from fastapi import APIRouter

from app.api.routes import (
    auth_router,
    health_router,
    onboarding_router,
    profile_router,
    students_router,
    sync_router,
    updates_router,
)

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(onboarding_router)
api_router.include_router(profile_router)
api_router.include_router(sync_router)
api_router.include_router(students_router)
api_router.include_router(updates_router)
