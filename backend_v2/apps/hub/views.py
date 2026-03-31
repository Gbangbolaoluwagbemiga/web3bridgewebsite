
from rest_framework import decorators, status, viewsets
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from . import serializers, models
from utils.helpers.requests import Utils as requestUtils
from drf_yasg.utils import swagger_auto_schema
from utils.helpers.mixins import GuestReadAllWriteAdminOnlyPermissionMixin
from .helpers.email import send_hub_admin_registration_email, send_hub_registration_email, send_hub_approval_email, send_hub_rejection_email
from .helpers.pagination import paginate_queryset


class HubSpaceViewSet(GuestReadAllWriteAdminOnlyPermissionMixin, viewsets.ViewSet):
    queryset = models.HubSpace.objects.all()
    serializer_class = serializers.HubSpaceSerializer
    admin_actions = ["create", "update", "destroy"]
    
    @swagger_auto_schema(request_body=serializers.HubSpaceSerializer.Create)
    def create(self, request, *args, **kwargs):
        """Create a new hub space (admin only)"""
        serializer = self.serializer_class.Create(data=request.data)
        
        if serializer.is_valid():
            hub_space_obj = serializer.save()
            serialized_obj = self.serializer_class.Retrieve(hub_space_obj).data
            return requestUtils.success_response(
                data=serialized_obj, 
                http_status=status.HTTP_201_CREATED
            )
        
        return requestUtils.error_response(
            "Error Creating Hub Space", 
            serializer.errors, 
            http_status=status.HTTP_400_BAD_REQUEST
        )
    
    @decorators.action(detail=False, methods=["get"])
    def all(self, request, *args, **kwargs):
        """Get hub spaces (paginated: page, limit; default limit 100, max 200)."""
        queryset = self.queryset.filter(is_active=True).order_by('-created_at')
        page_rows, pagination = paginate_queryset(request, queryset, default_limit=100, max_limit=200)
        serializer = self.serializer_class.List(page_rows, many=True)
        return requestUtils.success_response(
            data={"results": serializer.data, "pagination": pagination},
            http_status=status.HTTP_200_OK,
        )
    
    def retrieve(self, request, pk, *args, **kwargs):
        """Get a specific hub space"""
        try:
            hub_space_obj = self.queryset.get(pk=pk)
            serializer = self.serializer_class.Retrieve(hub_space_obj)
            return requestUtils.success_response(data=serializer.data, http_status=status.HTTP_200_OK)
        except models.HubSpace.DoesNotExist:
            return requestUtils.error_response(
                "Hub Space not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @swagger_auto_schema(request_body=serializers.HubSpaceSerializer.Update)
    def update(self, request, pk, *args, **kwargs):
        """Update hub space (admin only)"""
        try:
            hub_space_obj = self.queryset.get(pk=pk)
            serializer = self.serializer_class.Update(hub_space_obj, data=request.data)
            
            if serializer.is_valid():
                updated_obj = serializer.save()
                serialized_obj = self.serializer_class.Retrieve(updated_obj).data
                return requestUtils.success_response(
                    data=serialized_obj, 
                    http_status=status.HTTP_200_OK
                )
            
            return requestUtils.error_response(
                "Error Updating Hub Space", 
                serializer.errors, 
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except models.HubSpace.DoesNotExist:
            return requestUtils.error_response(
                "Hub Space not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    def destroy(self, request, pk, *args, **kwargs):
        """Delete a hub space (admin only)"""
        try:
            hub_space_obj = self.queryset.get(pk=pk)
            hub_space_obj.delete()
            return requestUtils.success_response(
                data={"message": "Hub Space deleted successfully"}, 
                http_status=status.HTTP_200_OK
            )
        except models.HubSpace.DoesNotExist:
            return requestUtils.error_response(
                "Hub Space not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @decorators.action(detail=False, methods=["get"])
    def stats(self, request, *args, **kwargs):
        """Get hub space statistics"""
        spaces = self.queryset.filter(is_active=True)
        agg = spaces.aggregate(
            total_capacity=Sum("total_capacity"),
            total_occupancy=Sum("current_occupancy"),
        )
        total_capacity = agg["total_capacity"] or 0
        total_occupancy = agg["total_occupancy"] or 0
        total_available = total_capacity - total_occupancy

        stats = {
            "total_spaces": spaces.count(),
            "total_capacity": total_capacity,
            "total_occupancy": total_occupancy,
            "total_available": total_available,
            "occupancy_percentage": (total_occupancy / total_capacity * 100) if total_capacity > 0 else 0,
        }

        return requestUtils.success_response(data=stats, http_status=status.HTTP_200_OK)


class HubRegistrationViewSet(GuestReadAllWriteAdminOnlyPermissionMixin, viewsets.ViewSet):
    queryset = models.HubRegistration.objects.all()
    serializer_class = serializers.HubRegistrationSerializer
    admin_actions = ["list", "retrieve", "update", "destroy", "approve", "reject"]
    
    @swagger_auto_schema(request_body=serializers.HubRegistrationSerializer.Create)
    def create(self, request, *args, **kwargs):
        """Create a new hub registration"""
        serializer = self.serializer_class.Create(data=request.data)

        print("serializer is valid", serializer.is_valid())


        if serializer.is_valid():
            hub_registration_obj = serializer.save()
            
            # Send registration confirmation email
            try:
                response = send_hub_registration_email(hub_registration_obj)
                response2 = send_hub_admin_registration_email(hub_registration_obj)
                print("response", response)
                print("response2", response2)
            except Exception as e:
                print(f"Error sending registration email: {str(e)}")
            
            serialized_obj = self.serializer_class.Retrieve(hub_registration_obj).data
            return requestUtils.success_response(
                data=serialized_obj, 
                http_status=status.HTTP_201_CREATED
            )
        
        return requestUtils.error_response(
            "Error Creating Hub Registration", 
            serializer.errors, 
            http_status=status.HTTP_400_BAD_REQUEST
        )
    
    @decorators.action(detail=False, methods=["get"])
    def all(self, request, *args, **kwargs):
        """Get recent hub registrations (last 90 days, excluding old rejected ones).

        Paginated: query params `page`, `limit` (default 100, max 200).
        """
        cutoff_date = timezone.now() - timedelta(days=90)

        queryset = self.queryset.filter(
            created_at__gte=cutoff_date
        ).exclude(
            Q(status=models.HubRegistration.REJECTED)
            & Q(created_at__lt=timezone.now() - timedelta(days=30))
        ).order_by('-created_at')

        page_rows, pagination = paginate_queryset(request, queryset, default_limit=100, max_limit=200)
        serializer = self.serializer_class.List(page_rows, many=True)
        return requestUtils.success_response(
            data={"results": serializer.data, "pagination": pagination},
            http_status=status.HTTP_200_OK,
        )
    
    def retrieve(self, request, pk, *args, **kwargs):
        """Get a specific hub registration"""
        try:
            hub_registration_obj = self.queryset.get(pk=pk)
            serializer = self.serializer_class.Retrieve(hub_registration_obj)
            return requestUtils.success_response(data=serializer.data, http_status=status.HTTP_200_OK)
        except models.HubRegistration.DoesNotExist:
            return requestUtils.error_response(
                "Hub Registration not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @swagger_auto_schema(request_body=serializers.HubRegistrationSerializer.Update)
    def update(self, request, pk, *args, **kwargs):
        """Update hub registration (admin only) - for approving/rejecting"""
        try:
            hub_registration_obj = self.queryset.get(pk=pk)
            old_status = hub_registration_obj.status
            serializer = self.serializer_class.Update(hub_registration_obj, data=request.data)
            
            if serializer.is_valid():
                updated_obj = serializer.save()
                
                # Send email if status changed
                new_status = updated_obj.status
                if old_status != new_status:
                    try:
                        if new_status == models.HubRegistration.APPROVED:
                            send_hub_approval_email(updated_obj)
                        elif new_status == models.HubRegistration.REJECTED:
                            send_hub_rejection_email(updated_obj)
                    except Exception as e:
                        print(f"Error sending status change email: {str(e)}")
                
                serialized_obj = self.serializer_class.Retrieve(updated_obj).data
                return requestUtils.success_response(
                    data=serialized_obj, 
                    http_status=status.HTTP_200_OK
                )
            
            return requestUtils.error_response(
                "Error Updating Hub Registration", 
                serializer.errors, 
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except models.HubRegistration.DoesNotExist:
            return requestUtils.error_response(
                "Hub Registration not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk, *args, **kwargs):
        """Approve a hub registration (admin only) - can re-approve checked_out registrations"""
        try:
            hub_registration_obj = self.queryset.get(pk=pk)
            
            if hub_registration_obj.status == models.HubRegistration.APPROVED:
                return requestUtils.error_response(
                    "Registration is already approved", 
                    {}, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # Allow re-approving checked_out registrations
            hub_registration_obj.status = models.HubRegistration.APPROVED
            hub_registration_obj.save()
            
            # Send approval email
            try:
                send_hub_approval_email(hub_registration_obj)
            except Exception as e:
                print(f"Error sending approval email: {str(e)}")
            
            serialized_obj = self.serializer_class.Retrieve(hub_registration_obj).data
            return requestUtils.success_response(
                data=serialized_obj, 
                http_status=status.HTTP_200_OK
            )
        except models.HubRegistration.DoesNotExist:
            return requestUtils.error_response(
                "Hub Registration not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @swagger_auto_schema(request_body=serializers.HubRegistrationSerializer.Update)
    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk, *args, **kwargs):
        """Reject a hub registration (admin only)"""
        try:
            hub_registration_obj = self.queryset.get(pk=pk)
            
            if hub_registration_obj.status == models.HubRegistration.REJECTED:
                return requestUtils.error_response(
                    "Registration is already rejected", 
                    {}, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get notes from request body if provided
            notes = request.data.get('notes', '')
            hub_registration_obj.status = models.HubRegistration.REJECTED
            if notes:
                hub_registration_obj.notes = notes
            hub_registration_obj.save()
            
            # Send rejection email
            try:
                send_hub_rejection_email(hub_registration_obj)
            except Exception as e:
                print(f"Error sending rejection email: {str(e)}")
            
            serialized_obj = self.serializer_class.Retrieve(hub_registration_obj).data
            return requestUtils.success_response(
                data=serialized_obj, 
                http_status=status.HTTP_200_OK
            )
        except models.HubRegistration.DoesNotExist:
            return requestUtils.error_response(
                "Hub Registration not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    def destroy(self, request, pk, *args, **kwargs):
        """Delete a hub registration (admin only)"""
        try:
            hub_registration_obj = self.queryset.get(pk=pk)
            hub_registration_obj.delete()
            return requestUtils.success_response(
                data={"message": "Hub Registration deleted successfully"}, 
                http_status=status.HTTP_200_OK
            )
        except models.HubRegistration.DoesNotExist:
            return requestUtils.error_response(
                "Hub Registration not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @decorators.action(detail=False, methods=["get"])
    def stats(self, request, *args, **kwargs):
        """Get registration statistics (admin only) - only recent data (last 90 days)"""
        # Only count recent registrations (last 90 days)
        cutoff_date = timezone.now() - timedelta(days=90)
        recent_queryset = self.queryset.filter(created_at__gte=cutoff_date)
        
        total = recent_queryset.count()
        pending = recent_queryset.filter(status='pending').count()
        approved = recent_queryset.filter(status='approved').count()
        rejected = recent_queryset.filter(status='rejected').count()
        checked_out = recent_queryset.filter(status='checked_out').count()
        
        stats = {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "checked_out": checked_out,
        }
        
        return requestUtils.success_response(data=stats, http_status=status.HTTP_200_OK)
    
    @decorators.action(detail=False, methods=["get"])
    def by_status(self, request, *args, **kwargs):
        """Get registrations by status (admin only) - only recent data (last 90 days).

        Paginated: `page`, `limit` (default 100, max 200).
        """
        cutoff_date = timezone.now() - timedelta(days=90)
        queryset = self.queryset.filter(created_at__gte=cutoff_date)

        status_filter = request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        queryset = queryset.order_by('-created_at')
        page_rows, pagination = paginate_queryset(request, queryset, default_limit=100, max_limit=200)
        serializer = self.serializer_class.List(page_rows, many=True)
        return requestUtils.success_response(
            data={"results": serializer.data, "pagination": pagination},
            http_status=status.HTTP_200_OK,
        )
    
    @decorators.action(detail=False, methods=["get"])
    def available_slots(self, request, *args, **kwargs):
        """Get available date/time slots for booking (public)"""
        from .helpers.availability import get_available_slots, get_time_slots
        from datetime import datetime, timedelta
        
        # Get query parameters
        start_date_str = request.query_params.get('start_date', None)
        end_date_str = request.query_params.get('end_date', None)
        space_id = request.query_params.get('space_id', None)
        
        start_date = None
        end_date = None
        
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return requestUtils.error_response(
                    "Invalid start_date format. Use YYYY-MM-DD",
                    {},
                    http_status=status.HTTP_400_BAD_REQUEST
                )
        
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return requestUtils.error_response(
                    "Invalid end_date format. Use YYYY-MM-DD",
                    {},
                    http_status=status.HTTP_400_BAD_REQUEST
                )
        
        space_id_int = None
        if space_id:
            try:
                space_id_int = int(space_id)
            except ValueError:
                return requestUtils.error_response(
                    "Invalid space_id. Must be an integer",
                    {},
                    http_status=status.HTTP_400_BAD_REQUEST
                )
        
        # Get available slots
        slots = get_available_slots(
            start_date=start_date,
            end_date=end_date,
            space_id=space_id_int
        )
        
        # Get time slots configuration
        time_slots = get_time_slots()
        
        return requestUtils.success_response(
            data={
                "available_slots": slots,
                "time_slots": time_slots,
                "total_available": len(slots)
            },
            http_status=status.HTTP_200_OK
        )


class CheckInViewSet(GuestReadAllWriteAdminOnlyPermissionMixin, viewsets.ViewSet):
    queryset = models.CheckIn.objects.all()
    serializer_class = serializers.CheckInSerializer
    admin_actions = ["list", "retrieve", "destroy"]
    
    @swagger_auto_schema(request_body=serializers.CheckInSerializer.Create)
    def create(self, request, *args, **kwargs):
        """Check in a visitor"""
        serializer = self.serializer_class.Create(data=request.data)
        
        if serializer.is_valid():
            checkin_obj = serializer.save()
            checkin_obj = self.queryset.select_related('registration', 'space').get(pk=checkin_obj.pk)
            serialized_obj = self.serializer_class.Retrieve(checkin_obj).data
            return requestUtils.success_response(
                data=serialized_obj, 
                http_status=status.HTTP_201_CREATED
            )
        
        return requestUtils.error_response(
            "Error Checking In", 
            serializer.errors, 
            http_status=status.HTTP_400_BAD_REQUEST
        )
    
    @decorators.action(detail=False, methods=["get"])
    def all(self, request, *args, **kwargs):
        """Get recent check-ins — last 30 days or all currently checked in.

        Uses select_related to avoid N+1 queries. Paginated: `page`, `limit` (default 100, max 200).
        """
        cutoff_date = timezone.now() - timedelta(days=30)
        queryset = (
            self.queryset.select_related('registration', 'space')
            .filter(Q(check_in_time__gte=cutoff_date) | Q(status=models.CheckIn.CHECKED_IN))
            .order_by('-check_in_time')
        )
        page_rows, pagination = paginate_queryset(request, queryset, default_limit=100, max_limit=200)
        serializer = self.serializer_class.List(page_rows, many=True)
        return requestUtils.success_response(
            data={"results": serializer.data, "pagination": pagination},
            http_status=status.HTTP_200_OK,
        )

    @decorators.action(detail=False, methods=["get"])
    def active(self, request, *args, **kwargs):
        """Get all currently checked-in visitors (paginated)."""
        queryset = (
            self.queryset.select_related('registration', 'space')
            .filter(status=models.CheckIn.CHECKED_IN)
            .order_by('-check_in_time')
        )
        page_rows, pagination = paginate_queryset(request, queryset, default_limit=100, max_limit=200)
        serializer = self.serializer_class.List(page_rows, many=True)
        return requestUtils.success_response(
            data={"results": serializer.data, "pagination": pagination},
            http_status=status.HTTP_200_OK,
        )
    
    def retrieve(self, request, pk, *args, **kwargs):
        """Get a specific check-in"""
        try:
            checkin_obj = self.queryset.select_related('registration', 'space').get(pk=pk)
            serializer = self.serializer_class.Retrieve(checkin_obj)
            return requestUtils.success_response(data=serializer.data, http_status=status.HTTP_200_OK)
        except models.CheckIn.DoesNotExist:
            return requestUtils.error_response(
                "Check-in not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @decorators.action(detail=True, methods=["post"])
    def check_out(self, request, pk, *args, **kwargs):
        """Check out a visitor"""
        try:
            checkin_obj = self.queryset.select_related('registration', 'space').get(pk=pk)

            if checkin_obj.status == models.CheckIn.CHECKED_OUT:
                return requestUtils.error_response(
                    "Visitor is already checked out", 
                    {}, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
            
            success = checkin_obj.check_out()

            if success:
                checkin_obj = self.queryset.select_related('registration', 'space').get(pk=checkin_obj.pk)
                serialized_obj = self.serializer_class.Retrieve(checkin_obj).data
                return requestUtils.success_response(
                    data=serialized_obj, 
                    http_status=status.HTTP_200_OK
                )
            else:
                return requestUtils.error_response(
                    "Error checking out", 
                    {}, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
        except models.CheckIn.DoesNotExist:
            return requestUtils.error_response(
                "Check-in not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @decorators.action(detail=False, methods=["post"])
    def check_out_by_registration(self, request, *args, **kwargs):
        """Check out by registration ID"""
        registration_id = request.data.get('registration_id')
        
        if not registration_id:
            return requestUtils.error_response(
                "registration_id is required", 
                {}, 
                http_status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            checkin_obj = (
                self.queryset.select_related('registration', 'space')
                .filter(
                    registration_id=registration_id,
                    status=models.CheckIn.CHECKED_IN,
                )
                .first()
            )

            if not checkin_obj:
                return requestUtils.error_response(
                    "No active check-in found for this registration", 
                    {}, 
                    http_status=status.HTTP_404_NOT_FOUND
                )
            
            success = checkin_obj.check_out()

            if success:
                checkin_obj = self.queryset.select_related('registration', 'space').get(pk=checkin_obj.pk)
                serialized_obj = self.serializer_class.Retrieve(checkin_obj).data
                return requestUtils.success_response(
                    data=serialized_obj, 
                    http_status=status.HTTP_200_OK
                )
            else:
                return requestUtils.error_response(
                    "Error checking out", 
                    {}, 
                    http_status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return requestUtils.error_response(
                "Error checking out", 
                {"error": str(e)}, 
                http_status=status.HTTP_400_BAD_REQUEST
            )
    
    def destroy(self, request, pk, *args, **kwargs):
        """Delete a check-in (admin only)"""
        try:
            checkin_obj = self.queryset.select_related('space').get(pk=pk)
            
            # If checked in, decrease occupancy before deleting
            if checkin_obj.status == models.CheckIn.CHECKED_IN and checkin_obj.space:
                checkin_obj.space.current_occupancy = max(0, checkin_obj.space.current_occupancy - 1)
                checkin_obj.space.save()
            
            checkin_obj.delete()
            return requestUtils.success_response(
                data={"message": "Check-in deleted successfully"}, 
                http_status=status.HTTP_200_OK
            )
        except models.CheckIn.DoesNotExist:
            return requestUtils.error_response(
                "Check-in not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @decorators.action(detail=False, methods=["get"])
    def stats(self, request, *args, **kwargs):
        """Get check-in statistics (admin only) - only recent data (last 30 days)"""
        # Only count recent check-ins (last 30 days) OR all currently checked in
        cutoff_date = timezone.now() - timedelta(days=30)
        recent_queryset = self.queryset.filter(
            Q(check_in_time__gte=cutoff_date) | Q(status=models.CheckIn.CHECKED_IN)
        )
        
        total = recent_queryset.count()
        checked_in = recent_queryset.filter(status=models.CheckIn.CHECKED_IN).count()
        checked_out = recent_queryset.filter(status=models.CheckIn.CHECKED_OUT).count()
        
        # Get today's stats
        
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_checkins = self.queryset.filter(check_in_time__gte=today_start).count()
        
        stats = {
            "total": total,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "today_checkins": today_checkins,
        }
        
        return requestUtils.success_response(data=stats, http_status=status.HTTP_200_OK)


class BlockedDateRangeViewSet(GuestReadAllWriteAdminOnlyPermissionMixin, viewsets.ViewSet):
    """ViewSet for managing blocked date ranges (admin only)"""
    queryset = models.BlockedDateRange.objects.all()
    serializer_class = serializers.BlockedDateRangeSerializer
    admin_actions = ["list", "retrieve", "create", "update", "destroy"]
    
    @swagger_auto_schema(request_body=serializers.BlockedDateRangeSerializer.Create)
    def create(self, request, *args, **kwargs):
        """Create a new blocked date range (admin only)"""
        serializer = self.serializer_class.Create(data=request.data)
        
        if serializer.is_valid():
            blocked_range_obj = serializer.save()
            serialized_obj = self.serializer_class.Retrieve(blocked_range_obj).data
            return requestUtils.success_response(
                data=serialized_obj, 
                http_status=status.HTTP_201_CREATED
            )
        
        return requestUtils.error_response(
            "Error Creating Blocked Date Range", 
            serializer.errors, 
            http_status=status.HTTP_400_BAD_REQUEST
        )
    
    @decorators.action(detail=False, methods=["get"])
    def all(self, request, *args, **kwargs):
        """Get all blocked date ranges (admin only)"""
        queryset = self.queryset.order_by('-start_date')
        serializer = self.serializer_class.List(queryset, many=True)
        return requestUtils.success_response(data=serializer.data, http_status=status.HTTP_200_OK)
    
    def list(self, request, *args, **kwargs):
        """Get all blocked date ranges (admin only)"""
        queryset = self.queryset.order_by('-start_date')
        serializer = self.serializer_class.List(queryset, many=True)
        return requestUtils.success_response(data=serializer.data, http_status=status.HTTP_200_OK)
    
    def retrieve(self, request, pk, *args, **kwargs):
        """Get a specific blocked date range (admin only)"""
        try:
            blocked_range_obj = self.queryset.get(pk=pk)
            serializer = self.serializer_class.Retrieve(blocked_range_obj)
            return requestUtils.success_response(data=serializer.data, http_status=status.HTTP_200_OK)
        except models.BlockedDateRange.DoesNotExist:
            return requestUtils.error_response(
                "Blocked Date Range not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    @swagger_auto_schema(request_body=serializers.BlockedDateRangeSerializer.Update)
    def update(self, request, pk, *args, **kwargs):
        """Update a blocked date range (admin only)"""
        try:
            blocked_range_obj = self.queryset.get(pk=pk)
            serializer = self.serializer_class.Update(blocked_range_obj, data=request.data)
            
            if serializer.is_valid():
                updated_obj = serializer.save()
                serialized_obj = self.serializer_class.Retrieve(updated_obj).data
                return requestUtils.success_response(
                    data=serialized_obj, 
                    http_status=status.HTTP_200_OK
                )
            
            return requestUtils.error_response(
                "Error Updating Blocked Date Range", 
                serializer.errors, 
                http_status=status.HTTP_400_BAD_REQUEST
            )
        except models.BlockedDateRange.DoesNotExist:
            return requestUtils.error_response(
                "Blocked Date Range not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )
    
    def destroy(self, request, pk, *args, **kwargs):
        """Delete a blocked date range (admin only)"""
        try:
            blocked_range_obj = self.queryset.get(pk=pk)
            blocked_range_obj.delete()
            return requestUtils.success_response(
                data={"message": "Blocked Date Range deleted successfully"}, 
                http_status=status.HTTP_200_OK
            )
        except models.BlockedDateRange.DoesNotExist:
            return requestUtils.error_response(
                "Blocked Date Range not found", 
                {}, 
                http_status=status.HTTP_404_NOT_FOUND
            )


class HubExportViewSet(GuestReadAllWriteAdminOnlyPermissionMixin, viewsets.ViewSet):
    """
    Full hub dataset for offline CSV / reporting.
    Requires admin auth (same as other hub write/admin operations).
    """

    admin_actions = ["datasets"]

    @swagger_auto_schema(
        operation_summary="Export all hub data as JSON (for CSV on the client)",
        operation_description=(
            "Returns spaces, registrations, check_ins, and blocked_date_ranges in one payload. "
            "Uses efficient values() queries (no N+1)."
        ),
    )
    @decorators.action(detail=False, methods=["get"], url_path="datasets")
    def datasets(self, request, *args, **kwargs):
        spaces = list(
            models.HubSpace.objects.order_by("id").values(
                "id",
                "name",
                "total_capacity",
                "current_occupancy",
                "is_active",
                "created_at",
                "updated_at",
            )
        )

        registrations = list(
            models.HubRegistration.objects.order_by("-created_at").values(
                "id",
                "name",
                "email",
                "phone_number",
                "location",
                "reason",
                "role",
                "contribution",
                "status",
                "notes",
                "preferred_date",
                "preferred_time",
                "expected_duration_hours",
                "created_at",
                "updated_at",
            )
        )

        checkin_rows = models.CheckIn.objects.order_by("-check_in_time").values(
            "id",
            "registration_id",
            "registration__name",
            "registration__email",
            "registration__phone_number",
            "space_id",
            "space__name",
            "status",
            "check_in_time",
            "check_out_time",
            "purpose",
            "notes",
            "created_at",
            "updated_at",
        )
        check_ins = [
            {
                "id": row["id"],
                "registration_id": row["registration_id"],
                "registration_name": row["registration__name"],
                "registration_email": row["registration__email"],
                "registration_phone": row["registration__phone_number"],
                "space_id": row["space_id"],
                "space_name": row["space__name"],
                "status": row["status"],
                "check_in_time": row["check_in_time"],
                "check_out_time": row["check_out_time"],
                "purpose": row["purpose"],
                "notes": row["notes"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in checkin_rows
        ]

        blocked_date_ranges = list(
            models.BlockedDateRange.objects.order_by("-start_date").values(
                "id",
                "start_date",
                "end_date",
                "reason",
                "is_active",
                "created_at",
                "updated_at",
            )
        )

        payload = {
            "exported_at": timezone.now().isoformat(),
            "spaces": spaces,
            "registrations": registrations,
            "check_ins": check_ins,
            "blocked_date_ranges": blocked_date_ranges,
        }
        return requestUtils.success_response(data=payload, http_status=status.HTTP_200_OK)
