from pydantic import BaseModel, EmailStr, Field


class ActivationRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthUserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    account_state: str


class AuthResponse(BaseModel):
    user: AuthUserResponse
    tokens: TokenResponse


class LogoutResponse(BaseModel):
    detail: str


class PasswordResetResponse(BaseModel):
    detail: str
    reset_token: str | None = None


class MessageResponse(BaseModel):
    detail: str
