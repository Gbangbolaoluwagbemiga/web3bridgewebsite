"""Tests for SyncService read operations (list, get, latest status)."""

from datetime import UTC, datetime

from fastapi import HTTPException

from app.models.portal import ExternalSyncRecord
from app.services.sync import SyncService


class DummyScalarResult:
    def __init__(
        self,
        values: list[ExternalSyncRecord] | None = None,
        value: ExternalSyncRecord | None = None,
    ) -> None:
        self._values = values or ([] if value is None else [value])
        self._value = value

    def all(self) -> list[ExternalSyncRecord]:
        return self._values

    def first(self) -> ExternalSyncRecord | None:
        return self._values[0] if self._values else None


class DummyExecuteResult:
    def __init__(
        self,
        values: list[ExternalSyncRecord] | None = None,
        value: ExternalSyncRecord | None = None,
    ) -> None:
        self._values = values
        self._value = value

    def scalars(self) -> DummyScalarResult:
        return DummyScalarResult(values=self._values, value=self._value)

    def scalar_one_or_none(self) -> ExternalSyncRecord | None:
        return self._value


class DummySession:
    def __init__(self, execute_result: DummyExecuteResult | None = None) -> None:
        self.added: list[object] = []
        self.commit_count = 0
        self.refresh_count = 0
        self.flush_count = 0
        self.execute_result = execute_result or DummyExecuteResult(values=[])

    def add(self, obj: object) -> None:
        if getattr(obj, "id", None) is None and type(obj).__name__ == "ExternalSyncRecord":
            obj.id = 41
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, obj: object) -> None:
        self.refresh_count += 1

    async def execute(self, statement: object) -> DummyExecuteResult:
        return self.execute_result


def build_record(record_id: int, job_name: str, status: str) -> ExternalSyncRecord:
    return ExternalSyncRecord(
        id=record_id,
        job_name=job_name,
        cursor="cursor-1",
        status=status,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        error_payload=None,
    )


async def test_list_sync_records_returns_all_records() -> None:
    records = [
        build_record(1, "cron_onboard_students", "success"),
        build_record(2, "cron_onboard_students", "failed"),
    ]
    session = DummySession(execute_result=DummyExecuteResult(values=records))
    service = SyncService(session)  # type: ignore[arg-type]

    response = await service.list_sync_records()

    assert [item.id for item in response] == [1, 2]


async def test_get_latest_sync_status_returns_latest_record() -> None:
    latest = build_record(3, "cron_onboard_students", "success")
    session = DummySession(execute_result=DummyExecuteResult(values=[latest]))
    service = SyncService(session)  # type: ignore[arg-type]

    response = await service.get_latest_sync_status(job_name="cron_onboard_students")

    assert response.job_name == "cron_onboard_students"
    assert response.latest_record is not None
    assert response.latest_record.id == 3


async def test_get_sync_record_raises_for_missing_record() -> None:
    session = DummySession(execute_result=DummyExecuteResult(value=None))
    service = SyncService(session)  # type: ignore[arg-type]

    try:
        await service.get_sync_record(record_id=404)
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Sync record not found"
    else:
        raise AssertionError("Expected missing sync record to raise 404")
