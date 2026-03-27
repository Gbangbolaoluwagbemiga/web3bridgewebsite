from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenType,
    create_access_token,
    create_activation_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.portal import (
    AccountState,
    AuditLog,
    OnboardingStatus,
    RefreshToken,
    StudentProfile,
    StudentStatusHistory,
    User,
)
from app.schemas.auth import (
    AuthResponse,
    AuthUserResponse,
    PasswordResetResponse,
    TokenResponse,
)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def login(self, *, email: str, password: str) -> AuthResponse:
        user = await self._get_user_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if user.account_state != AccountState.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )

        return await self._issue_tokens_for_user(user)

    async def activate_account(self, *, token: str, password: str) -> AuthResponse:
        payload = decode_token(token, expected_type=TokenType.ACTIVATION)
        user = await self.get_user_by_id(int(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        token_jti = str(payload.get("jti", ""))
        if not user.activation_token_jti or user.activation_token_jti != token_jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Activation token is invalid or already used",
            )

        if (
            user.activation_token_expires_at is not None
            and user.activation_token_expires_at <= datetime.now(UTC)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Activation token has expired",
            )

        if user.account_state in {AccountState.SUSPENDED.value, AccountState.DEACTIVATED.value}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account cannot be activated in its current state",
            )

        previous_account_state = user.account_state
        profile = await self._get_profile_by_user_id(user.id)
        previous_onboarding_status = profile.onboarding_status if profile is not None else None

        user.password_hash = hash_password(password)
        user.account_state = AccountState.ACTIVE.value
        user.activation_token_jti = None
        user.activation_token_expires_at = None

        if profile is not None:
            profile.onboarding_status = OnboardingStatus.COMPLETED.value

        if previous_account_state != AccountState.ACTIVE.value:
            self.session.add(
                StudentStatusHistory(
                    user_id=user.id,
                    from_state=previous_account_state,
                    to_state=AccountState.ACTIVE.value,
                    reason="account_activated",
                    changed_at=datetime.now(UTC),
                )
            )

        self.session.add(
            AuditLog(
                actor_user_id=user.id,
                action="account_activated",
                resource_type="user",
                resource_id=str(user.id),
                before_json={
                    "account_state": previous_account_state,
                    "onboarding_status": previous_onboarding_status,
                    "activation_token_jti": token_jti,
                },
                after_json={
                    "account_state": user.account_state,
                    "onboarding_status": (
                        profile.onboarding_status
                        if profile is not None
                        else previous_onboarding_status
                    ),
                    "activation_token_jti": user.activation_token_jti,
                },
                created_at=datetime.now(UTC),
            )
        )

        await self._revoke_all_user_refresh_tokens(user.id)
        await self.session.commit()
        await self.session.refresh(user)
        if profile is not None:
            await self.session.refresh(profile)
        return await self._issue_tokens_for_user(user)

    async def refresh(self, *, refresh_token: str) -> AuthResponse:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        user = await self.get_user_by_id(int(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        token_record = await self._get_refresh_token_record(payload["jti"])
        if token_record is None or token_record.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token revoked",
            )

        if token_record.expires_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        token_record.revoked_at = datetime.now(UTC)
        await self.session.commit()
        return await self._issue_tokens_for_user(user)

    async def logout(self, *, refresh_token: str) -> None:
        payload = decode_token(refresh_token, expected_type=TokenType.REFRESH)
        token_record = await self._get_refresh_token_record(payload["jti"])
        if token_record is None:
            return

        token_record.revoked_at = datetime.now(UTC)
        await self.session.commit()

    async def request_password_reset(self, *, email: str) -> PasswordResetResponse:
        user = await self._get_user_by_email(email)
        if user is None:
            return PasswordResetResponse(
                detail="If the account exists, a reset token has been issued"
            )

        reset_token, _, _ = create_password_reset_token(user_id=user.id, email=user.email)
        return PasswordResetResponse(
            detail="If the account exists, a reset token has been issued",
            reset_token=reset_token,
        )

    async def reset_password(self, *, token: str, new_password: str) -> None:
        payload = decode_token(token, expected_type=TokenType.PASSWORD_RESET)
        user = await self.get_user_by_id(int(payload["sub"]))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        user.password_hash = hash_password(new_password)
        await self._revoke_all_user_refresh_tokens(user.id)
        await self.session.commit()

    async def change_password(
        self,
        *,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

        user.password_hash = hash_password(new_password)
        await self._revoke_all_user_refresh_tokens(user.id)
        await self.session.commit()

    async def get_user_by_id(self, user_id: int) -> User | None:
        statement = select(User).where(User.id == user_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_activation_token_for_user(self, *, user: User) -> str:
        token, token_jti, expires_at = create_activation_token(user_id=user.id, email=user.email)
        user.activation_token_jti = token_jti
        user.activation_token_expires_at = expires_at
        await self.session.flush()
        return token

    async def _issue_tokens_for_user(self, user: User) -> AuthResponse:
        access_token, _, _ = create_access_token(user_id=user.id, email=user.email, role=user.role)
        refresh_token, refresh_jti, refresh_expires_at = create_refresh_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        )
        self.session.add(
            RefreshToken(
                user_id=user.id,
                jti=refresh_jti,
                expires_at=refresh_expires_at,
                created_at=datetime.now(UTC),
            )
        )
        user.last_login_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(user)

        return AuthResponse(
            user=AuthUserResponse(
                id=user.id,
                email=user.email,
                role=user.role,
                account_state=user.account_state,
            ),
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
        )

    async def _get_user_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email.lower())
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_profile_by_user_id(self, user_id: int) -> StudentProfile | None:
        statement = select(StudentProfile).where(StudentProfile.user_id == user_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _get_refresh_token_record(self, jti: str) -> RefreshToken | None:
        statement = select(RefreshToken).where(RefreshToken.jti == jti)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def _revoke_all_user_refresh_tokens(self, user_id: int) -> None:
        statement = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        result = await self.session.execute(statement)
        token_records = result.scalars().all()
        revoked_at = datetime.now(UTC)
        for token_record in token_records:
            token_record.revoked_at = revoked_at
