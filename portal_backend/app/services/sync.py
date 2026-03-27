from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.portal import AuditLog, ExternalSyncRecord, SyncJobStatus, User
from app.schemas.sync import (
    SyncRecordResponse,
    SyncStatusResponse,
    TriggerSyncRequest,
)

settings = get_settings()


class SyncService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def trigger_sync(
        self,
        *,
        actor: User,
        payload: TriggerSyncRequest,
    ) -> SyncRecordResponse:
        """Run the onboarding cron inline and return the result."""
        from app.cron.onboard_students import run_onboard_cron

        if payload.job_name != "cron_onboard_students":
            # Keep backward compatibility while making source-of-truth explicit.
            payload.job_name = "cron_onboard_students"

        # Run inline — no queue, no worker
        summary = await run_onboard_cron()

        # Fetch the record that run_onboard_cron created
        result = await self.session.execute(
            select(ExternalSyncRecord)
            .where(ExternalSyncRecord.job_name == "cron_onboard_students")
            .order_by(ExternalSyncRecord.id.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Sync completed but record not found",
            )

        self.session.add(
            AuditLog(
                actor_user_id=actor.id,
                action="sync_triggered_by_admin",
                resource_type="external_sync_record",
                resource_id=str(record.id),
                after_json=summary,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.commit()

        return self._build_sync_record_response(record)

    async def schedule_sync(self, *, payload: TriggerSyncRequest) -> SyncRecordResponse:
        """Run the onboarding cron inline (called by internal API key)."""
        from app.cron.onboard_students import run_onboard_cron

        if payload.job_name != "cron_onboard_students":
            payload.job_name = "cron_onboard_students"

        summary = await run_onboard_cron()

        result = await self.session.execute(
            select(ExternalSyncRecord)
            .where(ExternalSyncRecord.job_name == "cron_onboard_students")
            .order_by(ExternalSyncRecord.id.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

        if record is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Sync completed but record not found",
            )

        self.session.add(
            AuditLog(
                actor_user_id=None,
                action="sync_triggered_by_system",
                resource_type="external_sync_record",
                resource_id=str(record.id),
                after_json=summary,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.commit()

        return self._build_sync_record_response(record)

    async def list_sync_records(self) -> list[SyncRecordResponse]:
        statement = select(ExternalSyncRecord).order_by(ExternalSyncRecord.started_at.desc())
        result = await self.session.execute(statement)
        records = result.scalars().all()
        return [self._build_sync_record_response(record) for record in records]

    async def get_latest_sync_status(self, *, job_name: str) -> SyncStatusResponse:
        statement = (
            select(ExternalSyncRecord)
            .where(ExternalSyncRecord.job_name == job_name)
            .order_by(ExternalSyncRecord.started_at.desc(), ExternalSyncRecord.id.desc())
        )
        result = await self.session.execute(statement)
        record = result.scalars().first()
        return SyncStatusResponse(
            job_name=job_name,
            latest_record=(
                self._build_sync_record_response(record) if record is not None else None
            ),
        )

    async def get_sync_record(self, *, record_id: int) -> SyncRecordResponse:
        statement = select(ExternalSyncRecord).where(ExternalSyncRecord.id == record_id)
        result = await self.session.execute(statement)
        record = result.scalar_one_or_none()
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sync record not found"
            )
        return self._build_sync_record_response(record)

    @staticmethod
    def _build_sync_record_response(record: ExternalSyncRecord) -> SyncRecordResponse:
        return SyncRecordResponse(
            id=record.id,
            job_name=record.job_name,
            cursor=record.cursor,
            status=record.status,
            started_at=record.started_at,
            ended_at=record.ended_at,
            error_payload=record.error_payload,
        )
