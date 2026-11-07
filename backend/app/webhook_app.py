"""A deliberately tiny app that exposes ONLY the voice-agent webhook.

Point a public tunnel at THIS app, never at app.main. The full API has open
registration, payments, approvals and interactive docs; none of that should be
on the public internet. This app mounts one route (POST /agent-callbacks,
guarded by a shared secret) and a health check, with docs and the OpenAPI
schema switched off.

Run it:
    python -m uvicorn app.webhook_app:app --port 8001
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agent_callbacks import webhook_router
from app.config import settings, validate_production_settings
from app.core.middleware import (
    GlobalExceptionHandler,
    RateLimitMiddleware,
    RequestIDMiddleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings(settings)
    yield


app = FastAPI(
    title="Sangam agent webhook",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)
GlobalExceptionHandler.register(app)

app.include_router(webhook_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
