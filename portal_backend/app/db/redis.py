from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()
redis_client = Redis.from_url(settings.redis_dsn, decode_responses=True)


async def ping_redis() -> bool:
    return bool(await redis_client.ping())
