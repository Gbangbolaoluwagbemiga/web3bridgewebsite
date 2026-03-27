from fastapi import HTTPException

from app.core.security import (
    TokenType,
    create_activation_token,
    create_password_reset_token,
    decode_token,
    verify_password,
)
from app.models.portal import AccountState, OnboardingStatus, StudentProfile, User
from app.schemas.auth import AuthResponse, AuthUserResponse, TokenResponse
from app.services.auth import AuthService


def test_password_reset_token_roundtrip() -> None:
    token, _, _ = create_password_reset_token(user_id=7, email="reset@example.com")
    payload = decode_token(token, expected_type=TokenType.PASSWORD_RESET)

    assert payload["sub"] == "7"
    assert payload["email"] == "reset@example.com"
    assert payload["type"] == TokenType.PASSWORD_RESET


class DummySession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_count = 0
        self.refreshed: list[object] = []
        self.flush_count = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_count += 1

    async def flush(self) -> None:
        self.flush_count += 1

    async def refresh(self, obj: object) -> None:
        self.refreshed.append(obj)


async def test_create_activation_token_for_user_stores_latest_token_metadata() -> None:
    session = DummySession()
    service = AuthService(session)  # type: ignore[arg-type]
    user = User(
        id=21,
        email="invite@example.com",
        role="student",
        account_state=AccountState.INVITED.value,
    )

    token = await service.create_activation_token_for_user(user=user)
    payload = decode_token(token, expected_type=TokenType.ACTIVATION)

    assert user.activation_token_jti == payload["jti"]
    assert user.activation_token_expires_at is not None
    assert session.flush_count == 1


async def test_activate_account_marks_onboarding_completed_and_logs_history() -> None:
    session = DummySession()
    service = AuthService(session)  # type: ignore[arg-type]
    token, _, _ = create_activation_token(user_id=9, email="student@example.com")

    user = User(
        id=9,
        email="student@example.com",
        role="student",
        account_state=AccountState.INVITED.value,
    )
    user.activation_token_jti = decode_token(
        token,
        expected_type=TokenType.ACTIVATION,
    )["jti"]
    profile = StudentProfile(
        user_id=9,
        full_name="Student Example",
        onboarding_status=OnboardingStatus.INVITED.value,
    )
    user.activation_token_expires_at = None

    async def get_user(_: int) -> User:
        return user

    async def get_profile(_: int) -> StudentProfile:
        return profile

    async def revoke_tokens(_: int) -> None:
        return None

    async def issue_tokens(current_user: User) -> AuthResponse:
        return AuthResponse(
            user=AuthUserResponse(
                id=current_user.id,
                email=current_user.email,
                role=current_user.role,
                account_state=current_user.account_state,
            ),
            tokens=TokenResponse(access_token="access", refresh_token="refresh"),
        )

    service.get_user_by_id = get_user  # type: ignore[method-assign]
    service._get_profile_by_user_id = get_profile  # type: ignore[method-assign]
    service._revoke_all_user_refresh_tokens = revoke_tokens  # type: ignore[method-assign]
    service._issue_tokens_for_user = issue_tokens  # type: ignore[method-assign]

    response = await service.activate_account(token=token, password="SuperSecure123")

    assert response.user.account_state == AccountState.ACTIVE.value
    assert user.account_state == AccountState.ACTIVE.value
    assert user.activation_token_jti is None
    assert user.activation_token_expires_at is None
    assert profile.onboarding_status == OnboardingStatus.COMPLETED.value
    assert verify_password("SuperSecure123", user.password_hash) is True
    assert any(type(obj).__name__ == "StudentStatusHistory" for obj in session.added)
    assert any(type(obj).__name__ == "AuditLog" for obj in session.added)
    assert session.commit_count == 1


async def test_activate_account_does_not_duplicate_status_history_for_active_user() -> None:
    session = DummySession()
    service = AuthService(session)  # type: ignore[arg-type]
    token, _, _ = create_activation_token(user_id=11, email="active@example.com")

    user = User(
        id=11,
        email="active@example.com",
        role="student",
        account_state=AccountState.ACTIVE.value,
    )
    user.activation_token_jti = decode_token(token, expected_type=TokenType.ACTIVATION)["jti"]
    profile = StudentProfile(
        user_id=11,
        full_name="Active Student",
        onboarding_status=OnboardingStatus.INVITED.value,
    )
    user.activation_token_expires_at = None

    async def get_user(_: int) -> User:
        return user

    async def get_profile(_: int) -> StudentProfile:
        return profile

    async def revoke_tokens(_: int) -> None:
        return None

    async def issue_tokens(current_user: User) -> AuthResponse:
        return AuthResponse(
            user=AuthUserResponse(
                id=current_user.id,
                email=current_user.email,
                role=current_user.role,
                account_state=current_user.account_state,
            ),
            tokens=TokenResponse(access_token="access", refresh_token="refresh"),
        )

    service.get_user_by_id = get_user  # type: ignore[method-assign]
    service._get_profile_by_user_id = get_profile  # type: ignore[method-assign]
    service._revoke_all_user_refresh_tokens = revoke_tokens  # type: ignore[method-assign]
    service._issue_tokens_for_user = issue_tokens  # type: ignore[method-assign]

    response = await service.activate_account(token=token, password="AnotherPass123")

    assert response.user.account_state == AccountState.ACTIVE.value
    assert profile.onboarding_status == OnboardingStatus.COMPLETED.value
    assert not any(type(obj).__name__ == "StudentStatusHistory" for obj in session.added)
    assert any(type(obj).__name__ == "AuditLog" for obj in session.added)


async def test_activate_account_rejects_replayed_token() -> None:
    session = DummySession()
    service = AuthService(session)  # type: ignore[arg-type]
    token, _, _ = create_activation_token(user_id=14, email="replay@example.com")

    user = User(
        id=14,
        email="replay@example.com",
        role="student",
        account_state=AccountState.ACTIVE.value,
    )
    user.activation_token_jti = None
    user.activation_token_expires_at = None

    async def get_user(_: int) -> User:
        return user

    service.get_user_by_id = get_user  # type: ignore[method-assign]

    try:
        await service.activate_account(token=token, password="ReplayPass123")
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Activation token is invalid or already used"
    else:
        raise AssertionError("Expected replayed activation token to be rejected")
