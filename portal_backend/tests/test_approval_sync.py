"""Tests for cron onboard_students — the _onboard_student function."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.cron.onboard_students import _onboard_student
from app.models.portal import (
    AccountState,
    ExternalStudentMap,
    OnboardingStatus,
    StudentProfile,
    User,
    UserRole,
)


def _make_student_row(
    *,
    external_student_id=1001,
    email="student@example.com",
    full_name="Portal Student",
    course_name="Solidity Bootcamp",
    cohort="Cohort-XIV",
    phone="08012345678",
    wallet_address="0xabc",
    payment_status=True,
    source_status="ACCEPTED",
):
    return {
        "external_student_id": external_student_id,
        "email": email,
        "full_name": full_name,
        "course_name": course_name,
        "cohort": cohort,
        "phone": phone,
        "wallet_address": wallet_address,
        "payment_status": payment_status,
        "source_status": source_status,
        "source_updated_at": datetime(2026, 3, 10, 9, 30, tzinfo=UTC),
    }


class FakeScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, *, existing_map=None, existing_user=None, existing_profile=None):
        self._existing_map = existing_map
        self._existing_user = existing_user
        self._existing_profile = existing_profile
        self.added: list[object] = []
        self._call_count = 0
        self._next_id = 100

    async def execute(self, statement):
        self._call_count += 1
        # Return values in the order the function queries:
        # 1st: ExternalStudentMap lookup
        # 2nd: User by id (if map exists) or User by email
        # 3rd: User by email (if map user not found)
        # 4th: StudentProfile by user_id
        if self._call_count == 1:
            return FakeScalarResult(self._existing_map)
        elif self._call_count == 2:
            return FakeScalarResult(self._existing_user)
        elif self._call_count == 3:
            return FakeScalarResult(self._existing_profile)
        return FakeScalarResult(None)

    def add(self, obj):
        if isinstance(obj, User) and obj.id is None:
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def flush(self):
        pass


async def test_onboard_student_creates_new_user():
    session = FakeSession()
    email_service = AsyncMock()
    email_service.send_onboarding_email = AsyncMock(return_value=True)

    with patch("app.cron.onboard_students.create_activation_token") as mock_token:
        mock_token.return_value = ("token123", "jti123", datetime(2026, 3, 13, tzinfo=UTC))

        result = await _onboard_student(session, _make_student_row(), email_service)

    assert result == "created"

    users = [obj for obj in session.added if isinstance(obj, User)]
    assert len(users) == 1
    assert users[0].email == "student@example.com"
    assert users[0].account_state == AccountState.INVITED.value
    assert users[0].role == UserRole.STUDENT.value

    profiles = [obj for obj in session.added if isinstance(obj, StudentProfile)]
    assert len(profiles) == 1
    assert profiles[0].full_name == "Portal Student"
    assert profiles[0].onboarding_status == OnboardingStatus.INVITED.value

    maps = [obj for obj in session.added if isinstance(obj, ExternalStudentMap)]
    assert len(maps) == 1
    assert maps[0].external_student_id == "1001"

    email_service.send_onboarding_email.assert_called_once()


async def test_onboard_student_updates_existing_user():
    existing_user = User(
        id=9,
        email="student@example.com",
        role="student",
        account_state="active",
    )
    existing_profile = StudentProfile(
        user_id=9,
        full_name="Old Name",
        onboarding_status=OnboardingStatus.COMPLETED.value,
        cohort="Old Cohort",
    )

    session = FakeSession(existing_user=existing_user, existing_profile=existing_profile)
    email_service = AsyncMock()

    result = await _onboard_student(session, _make_student_row(), email_service)

    assert result == "updated"
    assert existing_profile.full_name == "Portal Student"
    assert existing_profile.cohort == "Cohort-XIV"
    # Should NOT send email for existing users
    email_service.send_onboarding_email.assert_not_called()


async def test_onboard_student_skips_zk_course():
    session = FakeSession()
    email_service = AsyncMock()

    result = await _onboard_student(
        session, _make_student_row(course_name="ZK Cohort XIV"), email_service
    )

    assert result == "skipped"
    assert session.added == []


async def test_onboard_student_skips_empty_email():
    session = FakeSession()
    email_service = AsyncMock()

    result = await _onboard_student(
        session, _make_student_row(email=""), email_service
    )

    assert result == "skipped"


async def test_onboard_student_skips_empty_name():
    session = FakeSession()
    email_service = AsyncMock()

    result = await _onboard_student(
        session, _make_student_row(full_name=""), email_service
    )

    assert result == "skipped"


async def test_onboard_student_normalizes_source_status_to_approval_status():
    session = FakeSession()
    email_service = AsyncMock()
    email_service.send_onboarding_email = AsyncMock(return_value=True)

    with patch("app.cron.onboard_students.create_activation_token") as mock_token:
        mock_token.return_value = ("token123", "jti123", datetime(2026, 3, 13, tzinfo=UTC))
        await _onboard_student(
            session,
            _make_student_row(source_status="accepted"),
            email_service,
        )

    maps = [obj for obj in session.added if isinstance(obj, ExternalStudentMap)]
    assert len(maps) == 1
    assert maps[0].approval_status == "approved"
