"""Redis client: rate limiting, short-lived locks and caching."""

import contextlib
import json
from typing import Any

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

log = structlog.get_logger(__name__)
_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def hit_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Fixed-window counter. Returns True when the limit is exceeded.

    Fails open (with a warning) if Redis is unavailable, so an outage of the cache
    does not take down authentication.
    """
    try:
        redis = get_redis()
        bucket = f"rl:{key}"
        count = await redis.incr(bucket)
        if count == 1:
            await redis.expire(bucket, window_seconds)
        return int(count) > limit
    except RedisError as exc:
        log.warning("rate_limit_unavailable", error=str(exc))
        return False


async def acquire_lock(key: str, ttl_seconds: int) -> bool:
    try:
        return bool(await get_redis().set(f"lock:{key}", "1", nx=True, ex=ttl_seconds))
    except RedisError as exc:
        log.warning("lock_unavailable", error=str(exc))
        return True  # the database constraints remain the source of truth


async def release_lock(key: str) -> None:
    with contextlib.suppress(RedisError):
        await get_redis().delete(f"lock:{key}")


async def cache_get(key: str) -> Any | None:
    try:
        raw = await get_redis().get(f"cache:{key}")
    except RedisError:
        return None
    return json.loads(raw) if raw else None


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    with contextlib.suppress(RedisError):
        await get_redis().set(f"cache:{key}", json.dumps(value, default=str), ex=ttl_seconds)


async def cache_delete(*keys: str) -> None:
    with contextlib.suppress(RedisError):
        await get_redis().delete(*(f"cache:{k}" for k in keys))
