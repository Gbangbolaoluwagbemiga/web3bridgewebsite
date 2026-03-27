import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.db.redis import redis_client

settings = get_settings()
logger = logging.getLogger(__name__)


async def _onboard_cron_loop() -> None:
    """Background loop that onboards paid non-ZK students on a fixed interval."""
    from app.cron.onboard_students import run_onboard_cron

    interval = settings.ONBOARD_CRON_INTERVAL_MINUTES * 60
    logger.info(
        "Onboard cron started — running every %d minutes", settings.ONBOARD_CRON_INTERVAL_MINUTES
    )

    while True:
        try:
            summary = await run_onboard_cron()
            logger.info("Onboard cron completed: %s", summary)
        except Exception:
            logger.exception("Onboard cron failed — will retry next interval")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cron_task = None
    if settings.ONBOARD_CRON_ENABLED:
        cron_task = asyncio.create_task(_onboard_cron_loop())

    yield

    if cron_task is not None:
        cron_task.cancel()
        try:
            await cron_task
        except asyncio.CancelledError:
            pass
    await redis_client.aclose()


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

app.include_router(api_router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
