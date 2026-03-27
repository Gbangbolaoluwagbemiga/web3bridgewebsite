from .auth import router as auth_router
from .health import router as health_router
from .onboarding import router as onboarding_router
from .profile import router as profile_router
from .sync import router as sync_router
from .students import router as students_router
from .updates import router as updates_router

__all__ = [
    "auth_router",
    "health_router",
    "onboarding_router",
    "profile_router",
    "sync_router",
    "students_router",
    "updates_router",
]
