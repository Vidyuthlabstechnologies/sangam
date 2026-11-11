"""The voice agent's callback webhook.

Sarvam calls this endpoint mid-call (and again if it retries) with what the
caller asked for. It is authenticated only by a shared secret, so these tests
pin the failure modes that matter: no secret means no write, a secret never
grants read access, retries do not create duplicates, and nothing that looks
like an Aadhaar number is ever stored.
"""
import uuid

import pytest
import pytest_asyncio

from app.config import settings
from app.models.actor import Role

SECRET = "test-webhook-secret-0123456789"
HOOK = {"X-Webhook-Secret": SECRET}
AADHAAR_LIKE = "2345 6789 0123"
_SCOPE = {"tenant": None}


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "agent_webhook_secret", SECRET, raising=False)


@pytest_asyncio.fixture(autouse=True)
async def _bind_callback_to_caller(current_actor, db_session):
    """Callbacks are only listed for a tenant the server can prove."""
    from app.core.billing_service import BillingService

    wallet = await BillingService(db_session).get_or_create_wallet(
        str(current_actor.id), owner_actor_id=current_actor.id, business_name=current_actor.name
    )
    await db_session.commit()
    await db_session.refresh(wallet)
    HOOK["X-Tenant-Key"] = wallet.metering_key
    _SCOPE["tenant"] = str(current_actor.id)
    yield
    HOOK.pop("X-Tenant-Key", None)
    _SCOPE["tenant"] = None


def _body(**over):
    body = {
        "caller_name": "Ravi Kumar",
        "caller_phone": "98765 43210",
        "service": "pan",
        "preferred_time": "tomorrow at 11",
        "language": "telugu",
        "urgency": "normal",
        "notes": "PAN name spelling correction",
        "call_id": f"call-{uuid.uuid4().hex[:12]}",
        "tenant_id": _SCOPE["tenant"],
    }
    body.update(over)
    return body


def _as_admin(current_actor):
    """Callback rows land on the pilot tenant. Only an admin may read that inbox."""
    current_actor.roles = [Role.ADMIN]


async def _find(client, auth_headers, call_id):
    resp = await client.get("/agent-callbacks", params={"limit": 100}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return next((r for r in resp.json() if r["call_id"] == call_id), None)


# ------------------------------------------------------------------- secret


@pytest.mark.asyncio
async def test_missing_secret_is_refused(client):
    resp = await client.post("/agent-callbacks", json=_body())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_is_refused(client):
    resp = await client.post(
        "/agent-callbacks", json=_body(), headers={"X-Webhook-Secret": "nope"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unconfigured_server_secret_refuses_everything(client, monkeypatch):
    monkeypatch.setattr(settings, "agent_webhook_secret", None)
    resp = await client.post("/agent-callbacks", json=_body(), headers=HOOK)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_the_webhook_secret_cannot_read_the_list(client):
    resp = await client.get("/agent-callbacks", headers=HOOK)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_listing_requires_a_logged_in_user(client):
    resp = await client.get("/agent-callbacks")
    assert resp.status_code in (401, 403)


# ----------------------------------------------------------------- recording


@pytest.mark.asyncio
async def test_records_a_callback_request(client, auth_headers, current_actor):
    _as_admin(current_actor)
    body = _body()
    resp = await client.post("/agent-callbacks", json=body, headers=HOOK)

    assert resp.status_code == 201, resp.text
    row = await _find(client, auth_headers, body["call_id"])
    assert row["caller_phone"] == "+919876543210"
    assert row["service"] == "pan"
    assert row["status"] == "new"
    assert row["urgency"] == "normal"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw", ["9876543210", "98765 43210", "+91 98765-43210", "919876543210"]
)
async def test_phone_numbers_are_normalised(client, auth_headers, current_actor, raw):
    _as_admin(current_actor)
    body = _body(caller_phone=raw)
    assert (await client.post("/agent-callbacks", json=body, headers=HOOK)).status_code == 201
    assert (await _find(client, auth_headers, body["call_id"]))["caller_phone"] == "+919876543210"


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["abc", "12345", "", "5876543210", "234567890123"])
async def test_things_that_are_not_phone_numbers_are_refused(client, raw):
    resp = await client.post("/agent-callbacks", json=_body(caller_phone=raw), headers=HOOK)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_aadhaar_like_numbers_are_masked_in_free_text(client, auth_headers, current_actor):
    _as_admin(current_actor)
    body = _body(
        notes=f"my aadhaar is {AADHAAR_LIKE} please update",
        caller_name="Ravi 234567890123",
    )
    assert (await client.post("/agent-callbacks", json=body, headers=HOOK)).status_code == 201

    row = await _find(client, auth_headers, body["call_id"])
    assert "[redacted]" in row["notes"]
    assert "[redacted]" in row["caller_name"]
    assert "6789" not in row["notes"] and "6789" not in row["caller_name"]


@pytest.mark.asyncio
async def test_unknown_service_is_stored_as_unclear(client, auth_headers, current_actor):
    _as_admin(current_actor)
    body = _body(service="driving licence")
    assert (await client.post("/agent-callbacks", json=body, headers=HOOK)).status_code == 201
    assert (await _find(client, auth_headers, body["call_id"]))["service"] == "unclear"


@pytest.mark.asyncio
async def test_bad_urgency_is_refused(client):
    resp = await client.post("/agent-callbacks", json=_body(urgency="asap"), headers=HOOK)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_retry_with_the_same_call_id_does_not_duplicate(client, auth_headers, current_actor):
    _as_admin(current_actor)
    body = _body()
    first = await client.post("/agent-callbacks", json=body, headers=HOOK)
    second = await client.post("/agent-callbacks", json=body, headers=HOOK)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    rows = (await client.get("/agent-callbacks", params={"limit": 100}, headers=auth_headers)).json()
    assert len([r for r in rows if r["call_id"] == body["call_id"]]) == 1


# --------------------------------------------------------- staff list/update


@pytest.mark.asyncio
async def test_list_is_newest_first_and_can_filter_by_status(client, auth_headers, current_actor):
    _as_admin(current_actor)
    older, newer = _body(), _body()
    first = (await client.post("/agent-callbacks", json=older, headers=HOOK)).json()["id"]
    await client.post("/agent-callbacks", json=newer, headers=HOOK)

    rows = (await client.get("/agent-callbacks", params={"limit": 100}, headers=auth_headers)).json()
    ids = [r["call_id"] for r in rows]
    assert ids.index(newer["call_id"]) < ids.index(older["call_id"])

    patched = await client.patch(
        f"/agent-callbacks/{first}", json={"status": "contacted"}, headers=auth_headers
    )
    assert patched.status_code == 200, patched.text

    new_only = (
        await client.get(
            "/agent-callbacks", params={"status": "new", "limit": 100}, headers=auth_headers
        )
    ).json()
    assert older["call_id"] not in [r["call_id"] for r in new_only]
    assert newer["call_id"] in [r["call_id"] for r in new_only]


@pytest.mark.asyncio
async def test_a_non_owner_cannot_read_or_update_another_tenants_callback(client, auth_headers, db_session):
    # The autouse fixture binds callbacks to the caller's own tenant, so prove
    # this one against a separate tenant the caller does not own.
    from app.core.billing_service import BillingService

    other_tenant = str(uuid.uuid4())
    other = await BillingService(db_session).get_or_create_wallet(other_tenant, business_name="Other business")
    await db_session.commit()
    await db_session.refresh(other)
    created = (
        await client.post(
            "/agent-callbacks",
            json=_body(tenant_id=other_tenant),
            headers={**HOOK, "X-Tenant-Key": other.metering_key},
        )
    ).json()
    listed = await client.get("/agent-callbacks", params={"limit": 100}, headers=auth_headers)
    assert listed.status_code == 200
    assert created["id"] not in [row["id"] for row in listed.json()]
    patched = await client.patch(
        f"/agent-callbacks/{created['id']}", json={"status": "closed"}, headers=auth_headers
    )
    assert patched.status_code == 404


@pytest.mark.asyncio
async def test_invalid_status_update_is_refused(client, auth_headers):
    created = (await client.post("/agent-callbacks", json=_body(), headers=HOOK)).json()
    resp = await client.patch(
        f"/agent-callbacks/{created['id']}", json={"status": "banana"}, headers=auth_headers
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_updating_an_unknown_callback_is_404(client, auth_headers):
    resp = await client.patch(
        f"/agent-callbacks/{uuid.uuid4()}", json={"status": "closed"}, headers=auth_headers
    )
    assert resp.status_code == 404
