import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings, validate_production_settings
from app.api.workflows import router as workflows_router
from app.api.actors import router as actors_router
from app.api.approvals import router as approvals_router
from app.api.coordination import router as coordination_router
from app.api.sarvam_ai import router as sarvam_router
from app.api.capabilities import router as capabilities_router
from app.api.payments import router as payments_router
from app.api.templates import router as templates_router
from app.api.mcp import router as mcp_router
from app.api.auth import router as auth_router
from app.api.ws import router as ws_router
from app.api.analytics import router as analytics_router
from app.api.notifications import router as notifications_router
from app.api.autonomous import router as autonomous_router
from app.api.govstack import router as govstack_router
from app.api.vendors import router as vendors_router
from app.api.voice import router as voice_router
from app.api.agent_callbacks import router as agent_callbacks_router
from app.api.agent_callbacks import webhook_router as agent_webhook_router
from app.api.onboarding import router as onboarding_router
from app.core.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    GlobalExceptionHandler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings(settings)
    await _ensure_billing_tables_and_seed()
    yield


async def _ensure_billing_tables_and_seed() -> None:
    """Create wallet/ledger tables if missing and seed the two pilot tenants. Never blocks startup."""
    import logging

    from app.core.billing_service import seed_live_tenants
    from app.db.base import Base
    from app.db.session import async_session_factory, engine
    from app.models import sangamitra_release  # noqa: F401  (registers the tables)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session_factory() as session:
            await seed_live_tenants(session)
    except Exception:
        logging.getLogger("sangam.startup").exception("Billing table setup/seed skipped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ApiV1AliasMiddleware:
    """Web calls `/api/v1/...`. Routers are mounted at the root, and `/api/v1` itself is the index."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if not path.startswith("/api/v1/"):
            await self.app(scope, receive, send)
            return

        scope = dict(scope)
        rewritten = path[len("/api/v1"):] or "/"
        scope["path"] = rewritten
        if scope.get("raw_path") is not None:
            scope["raw_path"] = rewritten.encode("ascii")

        async def send_aliased(message):
            if message["type"] == "http.response.start":
                headers = []
                for key, value in message.get("headers", []):
                    if key.lower() == b"location":
                        location = value.decode("latin1")
                        if location.startswith("/") and not location.startswith("/api/v1"):
                            value = f"/api/v1{location}".encode("latin1")
                    headers.append((key, value))
                message = dict(message)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_aliased)


app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiV1AliasMiddleware)

GlobalExceptionHandler.register(app)

app.include_router(workflows_router)
app.include_router(actors_router)
app.include_router(approvals_router)
app.include_router(coordination_router)
app.include_router(sarvam_router)
app.include_router(capabilities_router)
app.include_router(payments_router)
app.include_router(templates_router)
app.include_router(mcp_router)
app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(analytics_router)
app.include_router(notifications_router)
app.include_router(autonomous_router)
app.include_router(govstack_router)
app.include_router(vendors_router)
app.include_router(voice_router)
app.include_router(agent_callbacks_router)
app.include_router(agent_webhook_router)
app.include_router(onboarding_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "endpoints": {
            "workflows": "/workflows",
            "actors": "/actors",
            "approvals": "/approvals",
            "docs": "/docs",
            "health": "/health",
        },
    }
