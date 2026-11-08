"""Shared request limits.

In-process counters are wrong once more than one replica is running: each
process has its own window, so the configured limit is multiplied by the
replica count. When REDIS_URL is set, every replica increments the same
fixed window in Redis.

If Redis is configured but unreachable, the check fails open and logs.
A rate-limit store must not become an outage. Tests leave REDIS_URL empty
and exercise the Redis path with a fake client.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional, Protocol

from app.config import settings

logger = logging.getLogger("sangam.ratelimit")


class CounterClient(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> object: ...

    async def ping(self) -> bool: ...


class MemoryWindow:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, int]] = {}

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        window_start, count = self._buckets.get(key, (now, 0))
        if now - window_start > window_seconds:
            window_start = now
            count = 0
        if count >= limit:
            return False
        self._buckets[key] = (window_start, count + 1)
        return True


class RateLimiter:
    def __init__(self, redis: Optional[CounterClient] = None, memory: Optional[MemoryWindow] = None):
        self.redis = redis
        self.memory = memory or MemoryWindow()

    async def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        if self.redis is None:
            return self.memory.allow(key, limit, window_seconds)
        try:
            window_id = int(time.time()) // window_seconds
            redis_key = f"sangam:rl:{window_id}:{key}"
            count = int(await self.redis.incr(redis_key))
            if count == 1:
                await self.redis.expire(redis_key, window_seconds + 1)
            return count <= limit
        except Exception:
            # Do not log `key`: it contains the client address and the path.
            logger.warning("Redis rate limit unavailable; failing open")
            return True


_memory = MemoryWindow()
_redis_client: Any = None
_redis_url_loaded: Optional[str] = None


async def get_redis() -> Any:
    """Lazy shared client. Empty REDIS_URL keeps the process on memory."""
    global _redis_client, _redis_url_loaded
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    if _redis_client is not None and _redis_url_loaded == url:
        return _redis_client
    from redis.asyncio import Redis

    _redis_client = Redis.from_url(
        url,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
        decode_responses=True,
    )
    _redis_url_loaded = url
    return _redis_client


async def request_limiter() -> RateLimiter:
    return RateLimiter(redis=await get_redis(), memory=_memory)
