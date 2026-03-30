from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_admin_user,
    get_current_staff_or_admin_user,
    verify_internal_api_key,
)
from app.db.session import get_db_session
from app.models.portal import User
from app.schemas.sync import (
    SyncRecordResponse,
    SyncStatusResponse,
    TriggerSyncRequest,
)
from app.services.sync import SyncService

router = APIRouter(prefix="/sync", tags=["Sync"])


@router.post(
    "/jobs",
    response_model=SyncRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger sync manually",
    description=(
        "Run the DB-coupled onboarding cron inline (source of truth) "
        "and return the sync record. Admin only."
    ),
)
async def trigger_sync(
    payload: TriggerSyncRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> SyncRecordResponse:
    service = SyncService(db)
    return await service.trigger_sync(actor=current_user, payload=payload)


@router.post(
    "/jobs/schedule",
    response_model=SyncRecordResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Schedule sync (internal)",
    description=(
        "Run the DB-coupled onboarding cron inline (source of truth). "
        "Authenticated via X-Internal-API-Key header."
    ),
)
async def schedule_sync(
    payload: TriggerSyncRequest,
    _: str = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_db_session),
) -> SyncRecordResponse:
    service = SyncService(db)
    return await service.schedule_sync(payload=payload)


@router.get(
    "/jobs",
    response_model=list[SyncRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List sync records",
    description=(
        "Return all sync run records ordered by most recent. "
        "Staff or admin only."
    ),
)
async def list_sync_records(
    _: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[SyncRecordResponse]:
    service = SyncService(db)
    return await service.list_sync_records()


@router.get(
    "/jobs/{record_id}",
    response_model=SyncRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get sync record",
    description="Return a specific sync record by ID. Staff or admin only.",
)
async def get_sync_record(
    record_id: int,
    _: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> SyncRecordResponse:
    service = SyncService(db)
    return await service.get_sync_record(record_id=record_id)


@router.get(
    "/jobs/{job_name}/latest",
    response_model=SyncStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest sync status",
    description=(
        "Return the most recent sync record for a given job name. "
        "Staff or admin only."
    ),
)
async def get_latest_sync_status(
    job_name: str,
    _: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> SyncStatusResponse:
    service = SyncService(db)
    return await service.get_latest_sync_status(job_name=job_name)
