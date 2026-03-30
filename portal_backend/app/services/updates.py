from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal import (
    AuditLog,
    StudentProfile,
    StudentUpdate,
    StudentUpdateRead,
    UpdateTargetType,
    User,
)
from app.schemas.auth import MessageResponse
from app.schemas.updates import (
    CreateStudentUpdateRequest,
    MarkStudentUpdateReadResponse,
    StudentUpdateResponse,
    UpdateStudentUpdateRequest,
)


class UpdatesService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_update(
        self,
        *,
        actor: User,
        payload: CreateStudentUpdateRequest,
    ) -> StudentUpdateResponse:
        now = datetime.now(UTC)
        student_update = StudentUpdate(
            title=payload.title,
            body=payload.body,
            target_type=payload.target_type.value,
            target_ref=payload.target_ref,
            is_published=payload.is_published,
            published_at=now if payload.is_published else None,
            created_by=actor.id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(student_update)
        await self.session.flush()

        self.session.add(
            AuditLog(
                actor_user_id=actor.id,
                action="student_update_created",
                resource_type="student_update",
                resource_id=str(student_update.id),
                after_json=self._update_audit_snapshot(student_update),
                created_at=now,
            )
        )

        await self.session.commit()
        await self.session.refresh(student_update)
        return self._build_update_response(student_update=student_update)

    async def list_updates(self) -> list[StudentUpdateResponse]:
        updates = await self._list_all_updates()
        return [self._build_update_response(student_update=item) for item in updates]

    async def get_update(self, *, update_id: int) -> StudentUpdateResponse:
        student_update = await self._get_update_by_id(update_id)
        return self._build_update_response(student_update=student_update)

    async def update_update(
        self,
        *,
        actor: User,
        update_id: int,
        payload: UpdateStudentUpdateRequest,
    ) -> StudentUpdateResponse:
        student_update = await self._get_update_by_id(update_id)
        before_json = self._update_audit_snapshot(student_update)
        updates = payload.model_dump(exclude_unset=True)

        for field_name, value in updates.items():
            if field_name == "target_type" and value is not None:
                setattr(student_update, field_name, value.value)
                continue
            setattr(student_update, field_name, value)

        if payload.is_published is not None:
            student_update.published_at = datetime.now(UTC) if payload.is_published else None

        student_update.updated_at = datetime.now(UTC)

        self.session.add(
            AuditLog(
                actor_user_id=actor.id,
                action="student_update_updated",
                resource_type="student_update",
                resource_id=str(student_update.id),
                before_json=before_json,
                after_json=self._update_audit_snapshot(student_update),
                created_at=datetime.now(UTC),
            )
        )

        await self.session.commit()
        await self.session.refresh(student_update)
        return self._build_update_response(student_update=student_update)

    async def delete_update(self, *, actor: User, update_id: int) -> MessageResponse:
        student_update = await self._get_update_by_id(update_id)
        self.session.add(
            AuditLog(
                actor_user_id=actor.id,
                action="student_update_deleted",
                resource_type="student_update",
                resource_id=str(student_update.id),
                before_json=self._update_audit_snapshot(student_update),
                created_at=datetime.now(UTC),
            )
        )
        await self.session.delete(student_update)
        await self.session.commit()
        return MessageResponse(detail="Update deleted successfully")

    async def list_my_updates(self, *, user: User) -> list[StudentUpdateResponse]:
        profile = await self._get_profile_by_user_id(user.id)
        updates = await self._list_published_updates()
        visible_updates = [
            item
            for item in updates
            if self._update_applies_to_user(student_update=item, user=user, profile=profile)
        ]

        responses: list[StudentUpdateResponse] = []
        for item in visible_updates:
            read_record = await self._get_read_record(update_id=item.id, user_id=user.id)
            responses.append(
                self._build_update_response(
                    student_update=item,
                    read_at=read_record.read_at if read_record is not None else None,
                )
            )
        return responses

    async def mark_update_as_read(
        self,
        *,
        user: User,
        update_id: int,
    ) -> MarkStudentUpdateReadResponse:
        profile = await self._get_profile_by_user_id(user.id)
        student_update = await self._get_update_by_id(update_id)
        if not student_update.is_published or not self._update_applies_to_user(
            student_update=student_update,
            user=user,
            profile=profile,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Update not found")

        read_record = await self._get_read_record(update_id=update_id, user_id=user.id)
        if read_record is None:
            read_record = StudentUpdateRead(
                update_id=update_id,
                user_id=user.id,
                read_at=datetime.now(UTC),
            )
            self.session.add(read_record)
            await self.session.commit()
            await self.session.refresh(read_record)

        return MarkStudentUpdateReadResponse(
            detail="Update marked as read",
            read_at=read_record.read_at,
        )

    async def _list_all_updates(self) -> list[StudentUpdate]:
        statement = select(StudentUpdate).order_by(StudentUpdate.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def _list_published_updates(self) -> list[StudentUpdate]:
        statement = select(StudentUpdate).where(StudentUpdate.is_published.is_(True))
        statement = statement.order_by(
            StudentUpdate.published_at.desc(),
            StudentUpdate.created_at.desc(),
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def _get_update_by_id(self, update_id: int) -> StudentUpdate:
        statement = select(StudentUpdate).where(StudentUpdate.id == update_id)
        result = await self.session.execute(statement)
        student_update = result.scalar_one_or_none()
        if student_update is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Update not found")
        return student_update

    async def _get_profile_by_user_id(self, user_id: int) -> StudentProfile | None:
        statement = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_read_record(self, *, update_id: int, user_id: int) -> StudentUpdateRead | None:
        statement = select(StudentUpdateRead).where(
            StudentUpdateRead.update_id == update_id,
            StudentUpdateRead.user_id == user_id,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    def _update_applies_to_user(
        *,
        student_update: StudentUpdate,
        user: User,
        profile: StudentProfile | None,
    ) -> bool:
        if student_update.target_type == UpdateTargetType.ALL_ACTIVE.value:
            return True
        if student_update.target_type == UpdateTargetType.INDIVIDUAL.value:
            return student_update.target_ref == str(user.id)
        if student_update.target_type == UpdateTargetType.COHORT.value:
            return profile is not None and student_update.target_ref == profile.cohort
        return False

    @staticmethod
    def _build_update_response(
        *,
        student_update: StudentUpdate,
        read_at: datetime | None = None,
    ) -> StudentUpdateResponse:
        return StudentUpdateResponse(
            id=student_update.id,
            title=student_update.title,
            body=student_update.body,
            target_type=student_update.target_type,
            target_ref=student_update.target_ref,
            is_published=student_update.is_published,
            published_at=student_update.published_at,
            created_by=student_update.created_by,
            created_at=student_update.created_at,
            updated_at=student_update.updated_at,
            read_at=read_at,
        )

    @staticmethod
    def _update_audit_snapshot(student_update: StudentUpdate) -> dict[str, str | int | bool | None]:
        return {
            "title": student_update.title,
            "body": student_update.body,
            "target_type": student_update.target_type,
            "target_ref": student_update.target_ref,
            "is_published": student_update.is_published,
            "created_by": student_update.created_by,
        }
