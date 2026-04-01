import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError

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


app = FastAPI(title=settings.APP_NAME, debug=False, lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Flatten Pydantic 422 errors into a single human-readable detail string."""
    messages: list[str] = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        msg = error["msg"]
        messages.append(f"{field}: {msg}" if field else msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(messages)},
    )


@app.exception_handler(OperationalError)
@app.exception_handler(DBAPIError)
@app.exception_handler(ConnectionRefusedError)
@app.exception_handler(OSError)
async def db_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Return a clean 503 when the database is unreachable."""
    logger.exception("Database connection error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Service temporarily unavailable. Please try again later."},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all so the frontend always receives {detail: ...}."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


app.include_router(api_router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
