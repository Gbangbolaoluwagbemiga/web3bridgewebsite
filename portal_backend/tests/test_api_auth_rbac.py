from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.api import deps
from app.db.session import get_db_session
from app.main import app
from app.models.portal import AccountState, User
from app.schemas.profile import MyProfileResponse
from app.schemas.students import StudentResponse
from app.services.profile import ProfileService
from app.services.students import StudentsService


client = TestClient(app)


class DummyDBSession:
    pass


async def override_db_session() -> AsyncGenerator[DummyDBSession, None]:
    yield DummyDBSession()


def build_user(*, user_id: int, role: str, account_state: str) -> User:
    return User(
        id=user_id,
        email=f"{role}{user_id}@example.com",
        role=role,
        account_state=account_state,
    )


def clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_profile_route_requires_authentication() -> None:
    clear_overrides()

    response = client.get("/api/v1/me/profile")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_profile_route_rejects_inactive_user() -> None:
    clear_overrides()
    inactive_user = build_user(
        user_id=1,
        role="student",
        account_state=AccountState.INVITED.value,
    )

    async def override_current_user() -> User:
        return inactive_user

    app.dependency_overrides[deps.get_current_user] = override_current_user

    try:
        response = client.get("/api/v1/me/profile")
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is not active"


def test_profile_route_returns_profile_for_active_user() -> None:
    clear_overrides()
    active_user = build_user(
        user_id=2,
        role="student",
        account_state=AccountState.ACTIVE.value,
    )

    async def override_current_active_user() -> User:
        return active_user

    async def get_my_profile(_: ProfileService, *, user: User) -> MyProfileResponse:
        return MyProfileResponse(
            user_id=user.id,
            email=user.email,
            role=user.role,
            account_state=user.account_state,
            email_verified=True,
            full_name="Student Example",
            phone=None,
            discord_id=None,
            wallet_address=None,
            cohort="Cohort XIV",
            onboarding_status="completed",
            bio=None,
        )

    original_method = ProfileService.get_my_profile
    ProfileService.get_my_profile = get_my_profile
    app.dependency_overrides[deps.get_current_verified_user] = override_current_active_user
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        response = client.get("/api/v1/me/profile")
    finally:
        ProfileService.get_my_profile = original_method
        clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == 2
    assert payload["email"] == active_user.email
    assert payload["full_name"] == "Student Example"


def test_students_route_rejects_non_staff_user() -> None:
    clear_overrides()
    student_user = build_user(
        user_id=3,
        role="student",
        account_state=AccountState.ACTIVE.value,
    )

    async def override_current_active_user() -> User:
        return student_user

    app.dependency_overrides[deps.get_current_active_user] = override_current_active_user

    try:
        response = client.get("/api/v1/students")
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json()["detail"] == "Staff or admin access required"


def test_students_route_allows_staff_user() -> None:
    clear_overrides()
    staff_user = build_user(
        user_id=4,
        role="staff",
        account_state=AccountState.ACTIVE.value,
    )

    async def override_current_active_user() -> User:
        return staff_user

    async def list_students(_: StudentsService) -> list[StudentResponse]:
        return [
            StudentResponse(
                user_id=10,
                email="student10@example.com",
                role="student",
                account_state="active",
                full_name="Student Ten",
                phone=None,
                discord_id=None,
                wallet_address=None,
                cohort="Cohort XIV",
                onboarding_status="completed",
                bio=None,
            )
        ]

    original_method = StudentsService.list_students
    StudentsService.list_students = list_students
    app.dependency_overrides[deps.get_current_active_user] = override_current_active_user
    app.dependency_overrides[get_db_session] = override_db_session

    try:
        response = client.get("/api/v1/students")
    finally:
        StudentsService.list_students = original_method
        clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["user_id"] == 10
    assert payload[0]["full_name"] == "Student Ten"


def test_students_route_rejects_inactive_staff_user() -> None:
    clear_overrides()
    suspended_staff = build_user(
        user_id=5,
        role="staff",
        account_state=AccountState.SUSPENDED.value,
    )

    async def override_current_user() -> User:
        return suspended_staff

    app.dependency_overrides[deps.get_current_user] = override_current_user

    try:
        response = client.get("/api/v1/students")
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json()["detail"] == "Account is not active"
