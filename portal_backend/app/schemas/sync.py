from datetime import datetime

from pydantic import BaseModel, Field


class TriggerSyncRequest(BaseModel):
    job_name: str = Field(min_length=1, max_length=100)
    cursor: str | None = None


class SyncRecordResponse(BaseModel):
    id: int
    job_name: str
    cursor: str | None = None
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error_payload: dict | None = None


class SyncStatusResponse(BaseModel):
    job_name: str
    latest_record: SyncRecordResponse | None = None
