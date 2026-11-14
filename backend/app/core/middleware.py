from __future__ import annotations
import base64
import json
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


def client_ip(request: Request) -> str:
    """The client address for rate limiting, read so a client cannot choose it.

    With ``client_ip_forwarded_hop`` set, take that entry counted from the
    right of X-Forwarded-For, which the trusted proxy wrote. Never the left
    end: a client can put any address there.
    """
    hop = settings.client_ip_forwarded_hop
    if hop > 0:
        raw = ",".join(request.headers.getlist("x-forwarded-for"))
        hops = [h.strip() for h in raw.split(",") if h.strip()]
        if len(hops) >= hop:
            return hops[-hop]
    return request.client.host if request.client else "unknown"


def token_subject(request: Request) -> str | None:
    """The ``sub`` of the bearer token, read WITHOUT verifying it.

    Only used to pick a rate-limit bucket. A forged subject buys an attacker
    nothing but a fresh bucket of requests that then fail authentication, and
    the per-IP ceiling still caps them.
    """
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() != "bearer ":
        return None
    parts = auth[7:].strip().split(".")
    if len(parts) != 3 or len(parts[1]) > 4096:
        return None
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError):
        return None
    sub = claims.get("sub") if isinstance(claims, dict) else None
    if not isinstance(sub, str) or not sub or len(sub) > 128:
        return None
    return sub


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-account limits, with a generous per-IP ceiling.

    Indian mobile networks put thousands of subscribers behind one carrier-NAT
    address, so a tight per-IP limit would turn away real users. Signed-in
    requests are limited per account; anonymous ones per IP and path at a
    higher rate; and every request also counts toward a per-IP total that
    stops a single host from flooding.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        path = request.url.path
        if path in _SKIP_LIMITS:
            return await call_next(request)
        ip = client_ip(request)
        is_ai = any(path.startswith(p) for p in AI_PATHS)
        limiter = await request_limiter()
        # Keys are not logged. Redis shares them across replicas when configured.
        subject = token_subject(request)
        if subject is not None:
            key = f"u:{subject}:{path}"
            limit = settings.rate_limit_per_minute_ai if is_ai else settings.rate_limit_per_minute
        else:
            key = f"ip:{ip}:{path}"
            limit = settings.rate_limit_per_minute_ai if is_ai else settings.rate_limit_per_minute_anonymous
        allowed = await limiter.allow(f"ipall:{ip}", settings.rate_limit_per_ip_per_minute, 60)
        if allowed:
            allowed = await limiter.allow(key, limit, 60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


class GlobalExceptionHandler:
    @staticmethod
    def register(app: FastAPI) -> None:
        from app.core.govstack import LiveSourceUnavailable

        @app.exception_handler(LiveSourceUnavailable)
        async def handle_live_source_unavailable(request: Request, exc: LiveSourceUnavailable):
            return JSONResponse(
                status_code=503,
                content={"error": "source_unavailable", "detail": str(exc)},
            )

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
