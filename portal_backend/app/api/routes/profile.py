from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_verified_user
from app.db.session import get_db_session
from app.models.portal import User
from app.schemas.profile import MyProfileResponse, UpdateMyProfileRequest
from app.services.profile import ProfileService

router = APIRouter(prefix="/me", tags=["Profile"])


@router.get(
    "/profile",
    response_model=MyProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my profile",
    description=(
        "Return the authenticated student's full profile including "
        "name, phone, wallet address, cohort, and onboarding status."
    ),
)
async def get_my_profile(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db_session),
) -> MyProfileResponse:
    service = ProfileService(db)
    return await service.get_my_profile(user=current_user)


@router.patch(
    "/profile",
    response_model=MyProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update my profile",
    description=(
        "Update the authenticated student's profile. Editable "
        "fields: phone, discord_id, wallet_address, bio. "
        "Only provided fields are updated."
    ),
)
async def update_my_profile(
    payload: UpdateMyProfileRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db_session),
) -> MyProfileResponse:
    service = ProfileService(db)
    return await service.update_my_profile(user=current_user, payload=payload)
