"""Contract tests for backend_v2 -> portal_backend status normalization."""

from app.models.portal import ApprovalStatus
from app.services.status_mapping import normalize_approval_status


def test_backend_v2_aliases_map_to_portal_canonical_values() -> None:
    assert (
        normalize_approval_status("accepted", default=ApprovalStatus.PENDING.value)
        == ApprovalStatus.APPROVED.value
    )
    assert (
        normalize_approval_status("declined", default=ApprovalStatus.PENDING.value)
        == ApprovalStatus.REJECTED.value
    )
    assert (
        normalize_approval_status("suspended", default=ApprovalStatus.PENDING.value)
        == ApprovalStatus.REVOKED.value
    )


def test_unknown_status_falls_back_to_default() -> None:
    assert (
        normalize_approval_status("unexpected-status", default=ApprovalStatus.PENDING.value)
        == ApprovalStatus.PENDING.value
    )
