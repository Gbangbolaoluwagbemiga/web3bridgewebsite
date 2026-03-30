from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_or_admin_user
from app.db.session import get_db_session
from app.models.portal import User
from app.schemas.students import (
    ArchiveStudentRequest,
    StudentResponse,
    UpdateStudentRequest,
)
from app.services.students import StudentsService

router = APIRouter(prefix="/students", tags=["Students"])


@router.get(
    "",
    response_model=list[StudentResponse],
    status_code=status.HTTP_200_OK,
    summary="List all students",
    description="Return all student accounts. Staff or admin only.",
)
async def list_students(
    _: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[StudentResponse]:
    service = StudentsService(db)
    return await service.list_students()


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get student details",
    description="Return a single student's profile. Staff or admin only.",
)
async def get_student(
    student_id: int,
    _: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudentResponse:
    service = StudentsService(db)
    return await service.get_student(student_id=student_id)


@router.patch(
    "/{student_id}",
    response_model=StudentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update student",
    description=(
        "Update a student's profile or account state. Staff or "
        "admin only. Only provided fields are updated."
    ),
)
async def update_student(
    student_id: int,
    payload: UpdateStudentRequest,
    current_user: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudentResponse:
    service = StudentsService(db)
    return await service.update_student(
        actor=current_user, student_id=student_id, payload=payload
    )


@router.post(
    "/{student_id}/archive",
    response_model=StudentResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive student",
    description=(
        "Deactivate a student account. Sets account_state to "
        "DEACTIVATED. Staff or admin only."
    ),
)
async def archive_student(
    student_id: int,
    payload: ArchiveStudentRequest,
    current_user: User = Depends(get_current_staff_or_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudentResponse:
    service = StudentsService(db)
    return await service.archive_student(
        actor=current_user, student_id=student_id, payload=payload
    )
