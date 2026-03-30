from pydantic import BaseModel, Field

from app.models.portal import AccountState, OnboardingStatus


class StudentResponse(BaseModel):
    user_id: int
    email: str
    role: str
    account_state: str
    full_name: str | None = None
    phone: str | None = None
    discord_id: str | None = None
    wallet_address: str | None = None
    cohort: str | None = None
    onboarding_status: str | None = None
    bio: str | None = None


class UpdateStudentRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    discord_id: str | None = Field(default=None, max_length=100)
    wallet_address: str | None = Field(default=None, max_length=255)
    cohort: str | None = Field(default=None, max_length=100)
    onboarding_status: OnboardingStatus | None = None
    bio: str | None = None
    account_state: AccountState | None = None


class ArchiveStudentRequest(BaseModel):
    reason: str | None = Field(default="archived_by_staff", max_length=255)
