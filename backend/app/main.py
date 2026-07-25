import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
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
from app.core.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    GlobalExceptionHandler,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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

app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)

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
