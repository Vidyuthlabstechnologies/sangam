from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def engine_kwargs(
    url: str,
    *,
    debug: bool,
    pool_size: int,
    max_overflow: int,
    pool_timeout: int,
    pool_recycle: int,
    connect_timeout: int,
    command_timeout: int,
) -> dict:
    """Pool settings for Postgres. SQLite and debug stay on NullPool.

    asyncpg reads ``timeout`` as the connect timeout and ``command_timeout``
    as the per-command limit. Both come from the environment with defaults
    that fail a stuck connection instead of holding a worker forever.
    """
    if url.startswith("sqlite") or debug:
        return {"poolclass": NullPool, "echo": debug}

    connect_args: dict = {}
    if "+asyncpg" in url:
        connect_args = {
            "timeout": connect_timeout,
            "command_timeout": command_timeout,
        }
    return {
        "echo": debug,
        "pool_pre_ping": True,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_recycle": pool_recycle,
        "connect_args": connect_args,
    }


engine = create_async_engine(
    settings.database_url,
    **engine_kwargs(
        settings.database_url,
        debug=settings.debug,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        connect_timeout=settings.db_connect_timeout_seconds,
        command_timeout=settings.db_command_timeout_seconds,
    ),
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
