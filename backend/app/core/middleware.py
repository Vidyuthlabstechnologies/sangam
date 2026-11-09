from __future__ import annotations
import time
import uuid
import logging
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS, route_label
from app.core.rate_limit import request_limiter

logger = logging.getLogger("sangam.middleware")

_SKIP_LIMITS = {
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Server-to-server webhooks authenticate with a signature or shared secret
    # and arrive in bursts from a handful of provider IPs. A 429 would delay
    # crediting a customer's purchase.
    "/payments/webhook",
    "/billing/revenuecat/webhook",
}


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


AI_PATHS = {"/ai/speech-to-text", "/ai/text-to-speech", "/ai/llm", "/ai/vision/extract", "/ai/speech-to-text-translate"}


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        if request.url.path == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            path = route_label(request)
            HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
            HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - start)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        if request.url.path in _SKIP_LIMITS:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        is_ai = any(path.startswith(p) for p in AI_PATHS)
        limit = settings.rate_limit_per_minute_ai if is_ai else settings.rate_limit_per_minute
        limiter = await request_limiter()
        # The key is not logged. Redis shares it across replicas when configured.
        allowed = await limiter.allow(f"{client_ip}:{path}", limit, 60)
        if not allowed:
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
