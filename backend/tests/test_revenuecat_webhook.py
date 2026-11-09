"""Google Play purchases arrive through the RevenueCat webhook and credit the buyer's wallet."""
import uuid

import pytest

from app.config import settings
from tests.identity_tokens import mint_firebase_token

SECRET = "rc-webhook-test-secret-0123456789"


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "revenuecat_webhook_auth", SECRET)
    monkeypatch.setattr(settings, "revenuecat_accept_sandbox", True)


async def _signed_in_actor(client) -> tuple[str, dict]:
    token = mint_firebase_token(uid=f"buyer-{uuid.uuid4().hex[:16]}", name="Buyer")
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["actor_id"], headers


def _event(app_user_id: str, product_id: str, *, type_: str = "INITIAL_PURCHASE", txn: str | None = None,
           environment: str = "PRODUCTION") -> dict:
    return {
        "api_version": "1.0",
        "event": {
            "id": uuid.uuid4().hex,
            "type": type_,
            "app_user_id": app_user_id,
            "product_id": product_id,
            "transaction_id": txn or f"GPA.{uuid.uuid4().hex[:20]}",
            "environment": environment,
            "store": "PLAY_STORE",
        },
    }


async def _post(client, payload, auth=SECRET):
    headers = {"Authorization": auth} if auth is not None else {}
    return await client.post("/billing/revenuecat/webhook", json=payload, headers=headers)


async def _wallet(client, headers) -> dict:
    resp = await client.get("/onboarding/wallet/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_webhook_requires_the_shared_secret(client):
    actor_id, _ = await _signed_in_actor(client)
    payload = _event(actor_id, "vyapar:monthly")
    assert (await _post(client, payload, auth=None)).status_code == 401
    assert (await _post(client, payload, auth="wrong")).status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_everything_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "revenuecat_webhook_auth", None)
    actor_id, _ = await _signed_in_actor(client)
    assert (await _post(client, _event(actor_id, "vyapar:monthly"), auth="")).status_code == 401


@pytest.mark.asyncio
async def test_subscription_purchase_activates_plan_once(client):
    actor_id, headers = await _signed_in_actor(client)
    payload = _event(actor_id, "vyapar:monthly", txn="GPA.1111-2222-3333-44444")

    first = await _post(client, payload)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "credited"
    wallet = await _wallet(client, headers)
    assert wallet["plan_id"] == "vyapar"
    balance = wallet["call_balance_inr"]
    assert balance > 0

    # RevenueCat retries deliver the same transaction again.
    replay = await _post(client, payload)
    assert replay.status_code == 200
    assert replay.json()["status"] == "already_credited"
    assert (await _wallet(client, headers))["call_balance_inr"] == balance


@pytest.mark.asyncio
async def test_renewal_with_a_new_transaction_credits_again(client):
    actor_id, headers = await _signed_in_actor(client)
    await _post(client, _event(actor_id, "personal:monthly"))
    after_first = (await _wallet(client, headers))["call_balance_inr"]
    renewal = await _post(client, _event(actor_id, "personal:monthly", type_="RENEWAL"))
    assert renewal.json()["status"] == "credited"
    assert (await _wallet(client, headers))["call_balance_inr"] > after_first


@pytest.mark.asyncio
async def test_topup_and_pilot_one_time_products(client):
    actor_id, headers = await _signed_in_actor(client)
    pilot = await _post(client, _event(actor_id, "pilot", type_="NON_RENEWING_PURCHASE"))
    assert pilot.json()["status"] == "credited"
    before = (await _wallet(client, headers))["call_balance_inr"]
    topup = await _post(client, _event(actor_id, "topup_500", type_="NON_RENEWING_PURCHASE"))
    assert topup.json()["status"] == "credited"
    assert (await _wallet(client, headers))["call_balance_inr"] > before


@pytest.mark.asyncio
async def test_topup_works_before_any_plan(client):
    actor_id, headers = await _signed_in_actor(client)
    topup = await _post(client, _event(actor_id, "topup_500", type_="NON_RENEWING_PURCHASE"))
    assert topup.status_code == 200, topup.text
    assert topup.json()["status"] == "credited"
    assert (await _wallet(client, headers))["call_balance_inr"] > 0


@pytest.mark.parametrize(
    "app_user_id, product_id",
    [
        ("$RCAnonymousID:abc123", "vyapar:monthly"),
        (str(uuid.uuid4()), "vyapar:monthly"),
        (None, "unknown_product"),
    ],
    ids=["anonymous", "no-such-actor", "unmapped-product"],
)
@pytest.mark.asyncio
async def test_unknown_users_and_products_are_ignored_not_credited(client, app_user_id, product_id):
    if app_user_id is None:
        app_user_id, _ = await _signed_in_actor(client)
    resp = await _post(client, _event(app_user_id, product_id))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_lifecycle_events_do_not_touch_the_wallet(client):
    actor_id, headers = await _signed_in_actor(client)
    await _post(client, _event(actor_id, "vyapar:monthly"))
    before = await _wallet(client, headers)
    for event_type in ("CANCELLATION", "EXPIRATION", "BILLING_ISSUE", "TEST"):
        resp = await _post(client, _event(actor_id, "vyapar:monthly", type_=event_type))
        assert resp.json()["status"] == "ignored"
    assert (await _wallet(client, headers))["call_balance_inr"] == before["call_balance_inr"]


@pytest.mark.asyncio
async def test_sandbox_purchases_can_be_switched_off(client, monkeypatch):
    monkeypatch.setattr(settings, "revenuecat_accept_sandbox", False)
    actor_id, headers = await _signed_in_actor(client)
    resp = await _post(client, _event(actor_id, "vyapar:monthly", environment="SANDBOX"))
    assert resp.json()["status"] == "ignored"
