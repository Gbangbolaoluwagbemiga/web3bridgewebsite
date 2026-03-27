from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.redis import ping_redis
from app.db.session import get_db_session
from app.schemas.health import LiveHealthResponse, ReadyHealthResponse

router = APIRouter(prefix="/health", tags=["Health"])
settings = get_settings()


@router.get(
    "/live",
    response_model=LiveHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Returns OK if the server process is running.",
)
async def liveness() -> LiveHealthResponse:
    return LiveHealthResponse(
        status="ok",
        service=settings.APP_NAME,
        env=settings.APP_ENV,
    )


@router.get(
    "/ready",
    response_model=ReadyHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description=(
        "Checks database and Redis connectivity. Returns "
        "'ok' if both are reachable, 'degraded' otherwise."
    ),
)
async def readiness(
    db: AsyncSession = Depends(get_db_session),
) -> ReadyHealthResponse:
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    try:
        redis_ok = await ping_redis()
        if not redis_ok:
            redis_status = "down"
    except Exception:
        redis_status = "down"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return ReadyHealthResponse(
        status=overall, database=db_status, redis=redis_status
    )
