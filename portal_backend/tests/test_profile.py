from app.models.portal import AccountState, OnboardingStatus, StudentProfile, User
from app.schemas.profile import UpdateMyProfileRequest
from app.services.profile import ProfileService


class DummyResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class DummySession:
    def __init__(self, profile: StudentProfile | None) -> None:
        self.profile = profile
        self.added: list[object] = []
        self.commit_count = 0
        self.refreshed: list[object] = []

    async def execute(self, statement: object) -> DummyResult:
        return DummyResult(self.profile)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_count += 1

    async def refresh(self, obj: object) -> None:
        self.refreshed.append(obj)


def build_user() -> User:
    return User(
        id=5,
        email="student@example.com",
        role="student",
        account_state=AccountState.ACTIVE.value,
        email_verified=True,
    )


def build_profile() -> StudentProfile:
    return StudentProfile(
        id=7,
        user_id=5,
        full_name="Student Example",
        phone="08000000000",
        discord_id="student#1234",
        wallet_address="0x123",
        cohort="Cohort XIV",
        onboarding_status=OnboardingStatus.COMPLETED.value,
        bio="Hello world",
    )


async def test_get_my_profile_returns_profile_data() -> None:
    profile = build_profile()
    service = ProfileService(DummySession(profile))  # type: ignore[arg-type]

    response = await service.get_my_profile(user=build_user())

    assert response.user_id == 5
    assert response.email == "student@example.com"
    assert response.full_name == "Student Example"
    assert response.phone == "08000000000"
    assert response.onboarding_status == OnboardingStatus.COMPLETED.value


async def test_update_my_profile_updates_allowed_fields_and_logs_audit() -> None:
    profile = build_profile()
    session = DummySession(profile)
    service = ProfileService(session)  # type: ignore[arg-type]

    response = await service.update_my_profile(
        user=build_user(),
        payload=UpdateMyProfileRequest(
            phone="09000000000",
            discord_id="newstudent#9999",
            wallet_address="0xabc",
            bio="Updated bio",
        ),
    )

    assert profile.phone == "09000000000"
    assert profile.discord_id == "newstudent#9999"
    assert profile.wallet_address == "0xabc"
    assert profile.bio == "Updated bio"
    assert response.phone == "09000000000"
    assert response.discord_id == "newstudent#9999"
    assert response.wallet_address == "0xabc"
    assert response.bio == "Updated bio"
    assert any(type(obj).__name__ == "AuditLog" for obj in session.added)
    assert session.commit_count == 1
