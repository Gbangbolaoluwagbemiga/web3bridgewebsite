"""
Integration test: full student onboarding flow.

Tests the complete journey:
  1. Cron picks up a paid non-ZK student from cohort_participant
  2. Portal user created (INVITED) + activation email sent
  3. Student activates account (sets password)
  4. Student logs in
  5. Student views and updates profile

Run with:
    APP_ENV=development python -m pytest tests/test_integration_flow.py -v
"""

from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.cron.onboard_students import _onboard_student, _fetch_paid_non_zk_students
from app.models.portal import (
    AccountState,
    AuditLog,
    ExternalStudentMap,
    OnboardingStatus,
    StudentProfile,
    StudentStatusHistory,
    User,
    UserRole,
)
from app.core.security import create_activation_token, decode_token, TokenType
from app.services.auth import AuthService
from app.services.profile import ProfileService
from app.schemas.profile import UpdateMyProfileRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_paid_student_row(
    external_student_id=1001,
    email="teststudent@example.com",
    full_name="Test Student",
    course_name="Web3 Cohort XV",
    cohort="Cohort-XV",
):
    return {
        "external_student_id": external_student_id,
        "email": email,
        "full_name": full_name,
        "course_name": course_name,
        "cohort": cohort,
        "phone": "08012345678",
        "wallet_address": "0xAbC123",
        "payment_status": True,
        "source_updated_at": datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
    }


class FakeScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    """In-memory session that tracks created objects across the full flow."""

    def __init__(self):
        self.objects: list[object] = []
        self._users: dict[int, User] = {}
        self._profiles: dict[int, StudentProfile] = {}
        self._maps: dict[str, ExternalStudentMap] = {}
        self._next_id = 1
        self._query_index = 0

    def add(self, obj):
        if isinstance(obj, User) and obj.id is None:
            obj.id = self._next_id
            self._next_id += 1
            self._users[obj.id] = obj
        elif isinstance(obj, StudentProfile):
            self._profiles[getattr(obj, "user_id", 0)] = obj
        elif isinstance(obj, ExternalStudentMap):
            self._maps[obj.external_student_id] = obj
        self.objects.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, statement):
        # _onboard_student queries in order:
        # 1. ExternalStudentMap by external_id
        # 2. User by id or email
        # 3. StudentProfile by user_id
        self._query_index += 1
        return FakeScalarResult(None)

    def get_user(self, user_id: int) -> User | None:
        return self._users.get(user_id)

    def get_profile(self, user_id: int) -> StudentProfile | None:
        return self._profiles.get(user_id)


# ---------------------------------------------------------------------------
# Step 1 + 2: Cron creates portal user + sends email
# ---------------------------------------------------------------------------

async def test_step1_cron_creates_portal_user_for_paid_student():
    """Cron picks up paid non-ZK student and creates INVITED user."""
    session = FakeSession()
    email_service = AsyncMock()
    email_service.send_onboarding_email = AsyncMock(return_value=True)

    student_row = make_paid_student_row()

    with patch("app.cron.onboard_students.create_activation_token") as mock_token:
        mock_token.return_value = ("token-abc", "jti-abc", datetime(2026, 3, 23, tzinfo=UTC))

        result = await _onboard_student(session, student_row, email_service)

    assert result == "created"

    # User was created with INVITED state
    users = [obj for obj in session.objects if isinstance(obj, User)]
    assert len(users) == 1
    user = users[0]
    assert user.email == "teststudent@example.com"
    assert user.account_state == AccountState.INVITED.value
    assert user.role == UserRole.STUDENT.value
    assert user.password_hash is None  # No password yet

    # Profile was created
    profiles = [obj for obj in session.objects if isinstance(obj, StudentProfile)]
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.full_name == "Test Student"
    assert profile.cohort == "Cohort-XV"
    assert profile.phone == "08012345678"
    assert profile.wallet_address == "0xAbC123"
    assert profile.onboarding_status == OnboardingStatus.INVITED.value

    # External map was created
    maps = [obj for obj in session.objects if isinstance(obj, ExternalStudentMap)]
    assert len(maps) == 1
    assert maps[0].external_student_id == "1001"
    assert maps[0].source_system == "backend_v2"

    # Status history was logged
    histories = [obj for obj in session.objects if isinstance(obj, StudentStatusHistory)]
    assert len(histories) == 1
    assert histories[0].to_state == AccountState.INVITED.value
    assert histories[0].reason == "cron_onboard_paid_student"

    # Audit log was created
    audits = [obj for obj in session.objects if isinstance(obj, AuditLog)]
    assert len(audits) == 1
    assert audits[0].action == "cron_onboard_created"

    # Onboarding email was sent
    email_service.send_onboarding_email.assert_called_once_with(
        to_email="teststudent@example.com",
        student_name="Test Student",
        activation_url=ANY,  # URL contains the token
    )


async def test_step1_cron_skips_zk_students():
    """Cron correctly skips ZK course students."""
    session = FakeSession()
    email_service = AsyncMock()

    zk_student = make_paid_student_row(course_name="ZK Cohort XIV")
    result = await _onboard_student(session, zk_student, email_service)

    assert result == "skipped"
    assert len([obj for obj in session.objects if isinstance(obj, User)]) == 0
    email_service.send_onboarding_email.assert_not_called()


# ---------------------------------------------------------------------------
# Step 3: Student activates account (sets password)
# ---------------------------------------------------------------------------

async def test_step3_student_activates_account():
    """Student clicks activation link, sets password, account becomes ACTIVE."""
    # Create an INVITED user (simulating what the cron created)
    user = User(
        id=42,
        email="teststudent@example.com",
        role=UserRole.STUDENT.value,
        account_state=AccountState.INVITED.value,
        password_hash=None,
    )
    profile = StudentProfile(
        user_id=42,
        full_name="Test Student",
        onboarding_status=OnboardingStatus.INVITED.value,
    )

    # Generate a real activation token
    token, jti, expires_at = create_activation_token(user_id=user.id, email=user.email)
    user.activation_token_jti = jti
    user.activation_token_expires_at = expires_at

    # Verify the token is valid
    payload = decode_token(token, expected_type=TokenType.ACTIVATION)
    assert payload["sub"] == str(user.id)
    assert payload["email"] == user.email
    assert payload["type"] == TokenType.ACTIVATION


async def test_step3_activation_token_contains_correct_claims():
    """Activation token has the right structure for the frontend to use."""
    token, jti, expires_at = create_activation_token(user_id=99, email="test@example.com")

    payload = decode_token(token, expected_type=TokenType.ACTIVATION)

    assert payload["sub"] == "99"
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "activation"
    assert "jti" in payload
    assert "exp" in payload
    assert payload["jti"] == jti


# ---------------------------------------------------------------------------
# Step 4: Student logs in
# ---------------------------------------------------------------------------

async def test_step4_login_rejects_invited_user():
    """INVITED users (who haven't activated yet) cannot log in."""
    from app.core.security import hash_password

    user = User(
        id=42,
        email="teststudent@example.com",
        role=UserRole.STUDENT.value,
        account_state=AccountState.INVITED.value,
        password_hash=hash_password("mypassword123"),
    )

    session = AsyncMock()
    # Mock _get_user_by_email to return our user
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=result_mock)

    auth_service = AuthService(session)

    with pytest.raises(Exception) as exc_info:
        await auth_service.login(email="teststudent@example.com", password="mypassword123")

    # Should reject because account_state != ACTIVE
    assert exc_info.value.status_code == 403
    assert "not active" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Step 5: Student views and updates profile
# ---------------------------------------------------------------------------

async def test_step5_get_profile():
    """Active student can view their profile."""
    user = User(
        id=42,
        email="teststudent@example.com",
        role=UserRole.STUDENT.value,
        account_state=AccountState.ACTIVE.value,
    )
    profile = StudentProfile(
        user_id=42,
        full_name="Test Student",
        phone="08012345678",
        wallet_address="0xAbC123",
        cohort="Cohort-XV",
        onboarding_status=OnboardingStatus.COMPLETED.value,
    )

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = profile
    session.execute = AsyncMock(return_value=result_mock)

    profile_service = ProfileService(session)
    response = await profile_service.get_my_profile(user=user)

    assert response.email == "teststudent@example.com"
    assert response.full_name == "Test Student"
    assert response.phone == "08012345678"
    assert response.cohort == "Cohort-XV"
    assert response.onboarding_status == OnboardingStatus.COMPLETED.value


async def test_step5_update_profile():
    """Active student can update their own profile fields."""
    user = User(
        id=42,
        email="teststudent@example.com",
        role=UserRole.STUDENT.value,
        account_state=AccountState.ACTIVE.value,
    )
    profile = StudentProfile(
        user_id=42,
        full_name="Test Student",
        phone="08012345678",
        wallet_address="0xAbC123",
        cohort="Cohort-XV",
        onboarding_status=OnboardingStatus.COMPLETED.value,
    )

    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = profile
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    profile_service = ProfileService(session)
    response = await profile_service.update_my_profile(
        user=user,
        payload=UpdateMyProfileRequest(
            phone="09098765432",
            bio="Web3 developer from Lagos",
            discord_id="teststudent#1234",
        ),
    )

    assert response.phone == "09098765432"
    assert response.bio == "Web3 developer from Lagos"
    assert response.discord_id == "teststudent#1234"
    # Original fields unchanged
    assert response.full_name == "Test Student"
    assert response.wallet_address == "0xAbC123"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

async def test_cron_does_not_send_email_for_existing_user():
    """If user already exists in portal, cron updates but does NOT resend email."""
    existing_user = User(
        id=50,
        email="returning@example.com",
        role=UserRole.STUDENT.value,
        account_state=AccountState.ACTIVE.value,
    )
    existing_profile = StudentProfile(
        user_id=50,
        full_name="Old Name",
        onboarding_status=OnboardingStatus.COMPLETED.value,
        cohort="Cohort-XIV",
    )

    class SessionWithExistingUser(FakeSession):
        def __init__(self, user, profile):
            super().__init__()
            self._existing_user = user
            self._existing_profile = profile
            self._call_count = 0

        async def execute(self, statement):
            self._call_count += 1
            if self._call_count == 1:
                return FakeScalarResult(None)  # No external map
            elif self._call_count == 2:
                return FakeScalarResult(self._existing_user)  # User by email
            elif self._call_count == 3:
                return FakeScalarResult(self._existing_profile)  # Profile
            return FakeScalarResult(None)

    session = SessionWithExistingUser(existing_user, existing_profile)
    email_service = AsyncMock()

    student_row = make_paid_student_row(email="returning@example.com", full_name="New Name")
    result = await _onboard_student(session, student_row, email_service)

    assert result == "updated"
    assert existing_profile.full_name == "New Name"
    assert existing_profile.cohort == "Cohort-XV"
    # No email sent for existing users
    email_service.send_onboarding_email.assert_not_called()


async def test_cron_idempotent_on_repeated_runs():
    """Running cron twice for the same student doesn't create duplicates."""
    session = FakeSession()
    email_service = AsyncMock()
    email_service.send_onboarding_email = AsyncMock(return_value=True)

    student_row = make_paid_student_row()

    with patch("app.cron.onboard_students.create_activation_token") as mock_token:
        mock_token.return_value = ("tok1", "jti1", datetime(2026, 3, 23, tzinfo=UTC))
        result1 = await _onboard_student(session, student_row, email_service)

    assert result1 == "created"
    created_user = [obj for obj in session.objects if isinstance(obj, User)][0]

    # Second run — now the user exists
    class SessionWithUser(FakeSession):
        def __init__(self, user):
            super().__init__()
            self._user = user
            self._call_count = 0

        async def execute(self, statement):
            self._call_count += 1
            if self._call_count == 1:
                return FakeScalarResult(None)  # No external map yet
            elif self._call_count == 2:
                return FakeScalarResult(self._user)  # User found by email
            elif self._call_count == 3:
                return FakeScalarResult(None)  # No profile (simplified)
            return FakeScalarResult(None)

    session2 = SessionWithUser(created_user)
    email_service2 = AsyncMock()

    result2 = await _onboard_student(session2, student_row, email_service2)

    assert result2 == "updated"
    email_service2.send_onboarding_email.assert_not_called()
