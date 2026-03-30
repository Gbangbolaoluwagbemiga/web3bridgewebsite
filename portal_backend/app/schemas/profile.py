from pydantic import BaseModel, Field


class MyProfileResponse(BaseModel):
    user_id: int
    email: str
    role: str
    account_state: str
    email_verified: bool = False
    full_name: str
    phone: str | None = None
    discord_id: str | None = None
    wallet_address: str | None = None
    cohort: str | None = None
    onboarding_status: str
    bio: str | None = None


class UpdateMyProfileRequest(BaseModel):
    phone: str | None = Field(default=None, max_length=20)
    discord_id: str | None = Field(default=None, max_length=100)
    wallet_address: str | None = Field(default=None, max_length=255)
    bio: str | None = None
