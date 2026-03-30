import app.models  # noqa: F401
from app.db.base import Base

EXPECTED_TABLES = {
    "portal.audit_logs",
    "portal.external_student_map",
    "portal.external_sync_record",
    "portal.refresh_tokens",
    "portal.student_profiles",
    "portal.student_status_history",
    "portal.student_update_reads",
    "portal.student_updates",
    "portal.system_pings",
    "portal.users",
}


def test_portal_tables_are_registered() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))
