"""The app that sits behind the public tunnel must expose ONLY the webhook.

Putting the full API on a public URL would expose open registration, payments,
approvals and the interactive docs. The tunnel points at this small app
instead, which mounts the webhook plus health and readiness and nothing else.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db.session import get_session
from app.webhook_app import app as webhook_app

SECRET = "tunnel-test-secret-0123456789"


@pytest_asyncio.fixture
async def hook_client(db_session, monkeypatch):
    monkeypatch.setattr(settings, "agent_webhook_secret", SECRET, raising=False)

    async def override():
        yield db_session

    webhook_app.dependency_overrides[get_session] = override
    async with AsyncClient(transport=ASGITransport(app=webhook_app), base_url="http://test") as c:
        yield c
    webhook_app.dependency_overrides.clear()


def test_the_app_mounts_only_the_webhook_and_health():
    # Included routers are wrapper objects in recent FastAPI, so list paths via
    # the schema generator. The public /openapi.json URL is switched off, but
    # the generator itself still reports exactly what is mounted.
    assert set(webhook_app.openapi()["paths"]) == {
        "/agent-callbacks",
        "/agent-callbacks/call-ended",
        "/health",
        "/ready",
    }
    assert set(webhook_app.openapi()["paths"]["/agent-callbacks"]) == {"post"}
    assert set(webhook_app.openapi()["paths"]["/agent-callbacks/call-ended"]) == {"post"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/docs"),
        ("get", "/redoc"),
        ("get", "/openapi.json"),
        ("post", "/auth/register"),
        ("post", "/auth/login"),
        ("get", f"/payments/{uuid.uuid4()}"),
        ("get", "/workflows/"),
        ("patch", f"/agent-callbacks/{uuid.uuid4()}"),
    ],
)
async def test_nothing_else_is_reachable(hook_client, method, path):
    resp = await getattr(hook_client, method)(path)
    assert resp.status_code in (404, 405)


@pytest.mark.asyncio
async def test_staff_listing_is_not_exposed(hook_client):
    resp = await hook_client.get("/agent-callbacks", headers={"X-Webhook-Secret": SECRET})
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_health_answers(hook_client):
    resp = await hook_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_the_webhook_still_needs_the_secret(hook_client):
    body = {"caller_phone": "9876543210", "call_id": f"tunnel-{uuid.uuid4().hex[:8]}"}
    assert (await hook_client.post("/agent-callbacks", json=body)).status_code == 401


@pytest.mark.asyncio
async def test_the_webhook_records_with_the_secret(hook_client):
    body = {
        "caller_phone": "9876543210",
        "service": "pan",
        "call_id": f"tunnel-{uuid.uuid4().hex[:8]}",
    }
    resp = await hook_client.post(
        "/agent-callbacks", json=body, headers={"X-Webhook-Secret": SECRET}
    )
    assert resp.status_code == 201, resp.text
