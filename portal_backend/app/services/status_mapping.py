from app.models.portal import ApprovalStatus

_STATUS_ALIASES: dict[str, str] = {
    "accepted": ApprovalStatus.APPROVED.value,
    "approved": ApprovalStatus.APPROVED.value,
    "active": ApprovalStatus.APPROVED.value,
    "rejected": ApprovalStatus.REJECTED.value,
    "declined": ApprovalStatus.REJECTED.value,
    "revoked": ApprovalStatus.REVOKED.value,
    "suspended": ApprovalStatus.REVOKED.value,
    "pending": ApprovalStatus.PENDING.value,
    "in_review": ApprovalStatus.PENDING.value,
    "processing": ApprovalStatus.PENDING.value,
}


def normalize_approval_status(raw_status: str | None, *, default: str) -> str:
    normalized = (raw_status or "").strip().lower()
    if not normalized:
        return default
    return _STATUS_ALIASES.get(normalized, default)
