"""Liveness is process-up. Readiness checks the database, and Redis only when configured.

Failure responses name the check (`database`, `redis`) and nothing else.
Exception text can contain a connection URL, so it is logged as a fixed
message and never returned.
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.config import settings

logger = logging.getLogger("sangam.health")


async def database_ready() -> None:
    from app.db.session import engine

    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def redis_ready() -> None:
    from app.core.rate_limit import get_redis

    client = await get_redis()
    if client is None:
        return
    pong = await client.ping()
    if not pong:
        raise RuntimeError("redis ping failed")


async def collect_readiness() -> tuple[int, dict]:
    checks: dict[str, str] = {}
    try:
        await database_ready()
        checks["database"] = "ok"
    except Exception:
        logger.warning("readiness database check failed")
        checks["database"] = "unavailable"

    if (settings.redis_url or "").strip():
        try:
            await redis_ready()
            checks["redis"] = "ok"
        except Exception:
            logger.warning("readiness redis check failed")
            checks["redis"] = "unavailable"

    ok = all(value == "ok" for value in checks.values())
    return (200 if ok else 503), {"status": "ok" if ok else "unavailable", "checks": checks}
