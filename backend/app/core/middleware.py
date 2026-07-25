from __future__ import annotations
import time
import uuid
import logging
from typing import Callable, Dict, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import settings

logger = logging.getLogger("sangam.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s %s %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class RateLimitStore:
    def __init__(self):
        self._buckets: Dict[str, Tuple[float, int]] = {}

    def check(self, key: str, max_requests: int, window_seconds: int = 60, burst: int = 10) -> bool:
        now = time.monotonic()
        window_start, count = self._buckets.get(key, (now, 0))
        if now - window_start > window_seconds:
            window_start = now
            count = 0
        if count >= max_requests:
            return False
        count += 1
        self._buckets[key] = (window_start, count)
        return True


rate_limit_store = RateLimitStore()

AI_PATHS = {"/ai/speech-to-text", "/ai/text-to-speech", "/ai/llm", "/ai/vision/extract", "/ai/speech-to-text-translate"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        is_ai = any(path.startswith(p) for p in AI_PATHS)
        if is_ai:
            limit = settings.rate_limit_per_minute_ai
        else:
            limit = settings.rate_limit_per_minute
        if not rate_limit_store.check(f"{client_ip}:{path}", limit, 60, settings.rate_limit_burst):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": 60,
                },
            )
        return await call_next(request)


class GlobalExceptionHandler:
    @staticmethod
    def register(app: FastAPI) -> None:
        @app.exception_handler(Exception)
        async def handle_exception(request: Request, exc: Exception):
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "Unhandled exception [%s] %s %s: %s",
                request_id,
                request.method,
                request.url.path,
                str(exc),
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "detail": "An unexpected error occurred",
                    "request_id": request_id,
                },
            )
