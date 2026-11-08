"""Cross-customer reads and debits must fail on the shared deployment."""
import uuid

import pytest
from sqlalchemy import select

from app.config import settings
from app.core.billing_service import BillingService
from app.core.coordinator import Coordinator
from app.core.security import create_access_token
from app.models.actor import Actor, ActorType, Role
from app.models.vendor import Vendor
from app.models.workflow import Workflow

SECRET = "isolation-webhook-secret-0123456789"


async def _register(client, name: str):
    email = f"{name}-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "pass12345"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["actor_id"]


@pytest.mark.asyncio
async def test_actor_list_and_analytics_require_auth(client):
    actors = await client.get("/actors/")
    analytics = await client.get("/analytics/summary")
    assert actors.status_code in (401, 403)
    assert analytics.status_code in (401, 403)


@pytest.mark.asyncio
async def test_user_cannot_read_or_update_another_users_workflow(client):
    headers_a, actor_a = await _register(client, "alice")
    headers_b, _actor_b = await _register(client, "bob")

    created = await client.post(
        "/workflows/",
        json={"name": "Alice only", "initiator_id": _actor_b, "description": "private"},
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    assert created.json()["initiator_id"] == actor_a

    assert (await client.get(f"/workflows/{workflow_id}", headers=headers_b)).status_code == 404
    patched = await client.patch(
        f"/workflows/{workflow_id}", json={"name": "stolen"}, headers=headers_b
    )
    assert patched.status_code == 404
    listing = await client.get("/workflows/", headers=headers_b)
    assert workflow_id not in [item["id"] for item in listing.json()["items"]]


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_vendor(client):
    headers_a, _ = await _register(client, "vendor-a")
    headers_b, _ = await _register(client, "vendor-b")
    created = await client.post(
        "/vendors",
        json={"name": "Secret Supplies", "gstin": "29ABCDE1234F1Z5", "pan": "ABCDE1234F"},
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    vendor_id = created.json()["id"]

    assert (await client.get(f"/vendors/{vendor_id}", headers=headers_b)).status_code == 404
    listing = await client.get("/vendors", headers=headers_b)
    assert vendor_id not in [row["id"] for row in listing.json()]
    assert "29ABCDE1234F1Z5" not in listing.text


@pytest.mark.asyncio
async def test_user_cannot_read_or_patch_another_tenants_callback(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "agent_webhook_secret", SECRET)
    headers_a, actor_a = await _register(client, "call-a")
    headers_b, _actor_b = await _register(client, "call-b")
    wallet = await BillingService(db_session).get_or_create_wallet(actor_a, owner_actor_id=uuid.UUID(actor_a))
    await db_session.commit()
    await db_session.refresh(wallet)

    recorded = await client.post(
        "/agent-callbacks",
        json={
            "caller_name": "Private Caller",
            "caller_phone": "9876543210",
            "service": "pan",
            "call_id": f"iso-{uuid.uuid4().hex[:10]}",
            "tenant_id": actor_a,
        },
        headers={"X-Webhook-Secret": SECRET, "X-Tenant-Key": wallet.metering_key},
    )
    assert recorded.status_code == 201, recorded.text
    callback_id = recorded.json()["id"]

    listing = await client.get("/agent-callbacks", headers=headers_b)
    assert listing.status_code == 200
    assert callback_id not in [row["id"] for row in listing.json()]
    assert "9876543210" not in listing.text
    foreign = await client.get("/agent-callbacks", params={"tenant_id": actor_a}, headers=headers_b)
    assert foreign.status_code == 404
    patched = await client.patch(
        f"/agent-callbacks/{callback_id}", json={"status": "closed"}, headers=headers_b
    )
    assert patched.status_code == 404
    own = await client.get("/agent-callbacks", headers=headers_a)
    assert callback_id in [row["id"] for row in own.json()]


@pytest.mark.asyncio
async def test_user_cannot_read_or_create_an_approval_on_another_workflow(client):
    headers_a, actor_a = await _register(client, "appr-a")
    headers_b, _actor_b = await _register(client, "appr-b")
    workflow = await client.post("/workflows/", json={"name": "Needs approval"}, headers=headers_a)
    workflow_id = workflow.json()["id"]
    created = await client.post(
        "/approvals/",
        json={"workflow_id": workflow_id, "required_actors": [actor_a], "strategy": "all"},
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    approval_id = created.json()["id"]

    assert (await client.get(f"/approvals/{approval_id}", headers=headers_b)).status_code == 404
    forged = await client.post(
        "/approvals/",
        json={"workflow_id": workflow_id, "required_actors": [_actor_b], "strategy": "any"},
        headers=headers_b,
    )
    assert forged.status_code == 404


@pytest.mark.asyncio
async def test_forged_webhook_tenant_does_not_debit_the_other_wallet(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "agent_webhook_secret", SECRET)
    alice = Actor(id=uuid.uuid4(), type=ActorType.HUMAN, name="Alice", roles=[Role.INITIATOR], permissions=[])
    bob = Actor(id=uuid.uuid4(), type=ActorType.HUMAN, name="Bob", roles=[Role.INITIATOR], permissions=[])
    db_session.add_all([alice, bob])
    await db_session.commit()
    svc = BillingService(db_session)
    alice_wallet = await svc.get_or_create_wallet(str(alice.id), owner_actor_id=alice.id)
    bob_wallet = await svc.get_or_create_wallet(str(bob.id), owner_actor_id=bob.id)
    alice_wallet.call_balance_paise = 100_000
    bob_wallet.call_balance_paise = 100_000
    alice_wallet.deployment_status = "ACTIVE"
    bob_wallet.deployment_status = "ACTIVE"
    await db_session.commit()

    secret_only = await client.post(
        "/agent-callbacks/call-ended",
        json={"call_id": "forge-secret", "tenant_id": str(bob.id), "duration_seconds": 60},
        headers={"X-Webhook-Secret": SECRET},
    )
    assert secret_only.status_code == 403
    wrong_key = await client.post(
        "/agent-callbacks/call-ended",
        json={"call_id": "forge-key", "tenant_id": str(bob.id), "duration_seconds": 60},
        headers={"X-Webhook-Secret": SECRET, "X-Tenant-Key": alice_wallet.metering_key},
    )
    assert wrong_key.status_code == 403
    await db_session.refresh(bob_wallet)
    assert bob_wallet.call_balance_paise == 100_000

    legit = await client.post(
        "/agent-callbacks/call-ended",
        json={"call_id": "alice-real", "tenant_id": str(alice.id), "duration_seconds": 60},
        headers={"X-Webhook-Secret": SECRET, "X-Tenant-Key": alice_wallet.metering_key},
    )
    assert legit.status_code == 200, legit.text
    await db_session.refresh(alice_wallet)
    assert alice_wallet.call_balance_paise < 100_000
    await db_session.refresh(bob_wallet)
    assert bob_wallet.call_balance_paise == 100_000


@pytest.mark.asyncio
async def test_notification_test_cannot_target_another_actor(client):
    headers_a, _actor_a = await _register(client, "note-a")
    _headers_b, actor_b = await _register(client, "note-b")
    resp = await client.post(
        "/notifications/test",
        json={"actor_id": actor_b, "title": "hi", "body": "there"},
        headers=headers_a,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_refresh_rejects_an_inactive_actor(client, db_session):
    _headers, actor_id = await _register(client, "sleepy")
    actor = (
        await db_session.execute(select(Actor).where(Actor.id == uuid.UUID(actor_id)))
    ).scalar_one()
    token = create_access_token(actor_id)
    actor.is_active = False
    await db_session.commit()
    resp = await client.post("/auth/refresh", json={"token": token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cannot_grant_yourself_admin(client):
    headers, actor_id = await _register(client, "climber")
    created = await client.post(
        "/actors/",
        json={"type": "human", "name": "Ops", "roles": ["admin"], "permissions": ["manage:actors"]},
        headers=headers,
    )
    assert created.status_code == 403
    patched = await client.patch(
        f"/actors/{actor_id}",
        json={"roles": ["admin"]},
        headers=headers,
    )
    assert patched.status_code == 403


@pytest.mark.asyncio
async def test_account_deletion_removes_owned_personal_data_and_keeps_shared_workflows(
    client, db_session
):
    headers_a, actor_a = await _register(client, "delete-me")
    headers_b, actor_b = await _register(client, "stays")
    vendor = await client.post("/vendors", json={"name": "Mine", "pan": "ABCDE1234F"}, headers=headers_a)
    assert vendor.status_code == 201, vendor.text
    own_workflow = await client.post("/workflows/", json={"name": "Solo notes"}, headers=headers_a)
    shared = await client.post("/workflows/", json={"name": "Shared deal"}, headers=headers_a)
    await Coordinator(db_session).create_handoff(
        workflow_id=uuid.UUID(shared.json()["id"]),
        from_actor_id=uuid.UUID(actor_a),
        to_actor_id=uuid.UUID(actor_b),
        artifact="coa",
    )
    bob_workflow = await client.post("/workflows/", json={"name": "Bob's book"}, headers=headers_b)

    deleted = await client.delete(f"/onboarding/delete-account/{actor_a}", headers=headers_a)
    assert deleted.status_code == 200, deleted.text
    items = set(deleted.json()["deleted_items"])
    assert "actor_credentials" in items
    assert "vendors" in items
    assert "owned_workflows" in items

    actor = (
        await db_session.execute(select(Actor).where(Actor.id == uuid.UUID(actor_a)))
    ).scalar_one()
    assert actor.is_active is False
    assert actor.email is None
    assert actor.password_hash is None
    assert (actor.extra_attributes or {}).get("fcm_tokens") in (None, [])

    solo = (
        await db_session.execute(select(Workflow).where(Workflow.id == uuid.UUID(own_workflow.json()["id"])))
    ).scalar_one()
    assert solo.name == "Deleted workflow"
    shared_row = (
        await db_session.execute(select(Workflow).where(Workflow.id == uuid.UUID(shared.json()["id"])))
    ).scalar_one()
    assert shared_row.name == "Shared deal"
    bob_row = (
        await db_session.execute(select(Workflow).where(Workflow.id == uuid.UUID(bob_workflow.json()["id"])))
    ).scalar_one()
    assert bob_row.name == "Bob's book"
    assert (
        await db_session.execute(select(Vendor).where(Vendor.id == uuid.UUID(vendor.json()["id"])))
    ).scalar_one_or_none() is None

    refresh = await client.post(
        "/auth/refresh",
        json={"token": headers_a["Authorization"].split()[1]},
    )
    assert refresh.status_code == 401
