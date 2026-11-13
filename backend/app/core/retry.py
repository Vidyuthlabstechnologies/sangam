from __future__ import annotations
import asyncio
import functools
import logging
from typing import Type, Tuple, Optional, Callable, Any

logger = logging.getLogger("sangam.retry")


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exc = e
            if attempt < max_retries:
                delay = min(base_delay * (backoff ** attempt), max_delay)
                logger.warning(
                    "Retry %s/%s for %s after %.1fs: %s",
                    attempt + 1, max_retries, func.__name__, delay, e,
                )
                await asyncio.sleep(delay)
    if last_exc is None:
        raise RuntimeError(f"{func.__name__} was not attempted (max_retries={max_retries})")
    raise last_exc


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_async(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff=backoff,
                retryable_exceptions=retryable_exceptions,
                **kwargs,
            )
        return wrapper
    return decorator
