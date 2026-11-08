"""Wallet, plans, payments, metering and tenant-isolation tests.

These exist because the first version of this code let any anonymous caller credit any
wallet for free, read any business's balance, and kept all balances in process memory.
"""
import hashlib
import hmac
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.api.dependencies import get_current_actor
from app.config import settings
from app.core import pricing
from app.core.billing_service import seed_live_tenants
from app.main import app
from app.models.actor import Actor, ActorType, Role

RZP_SECRET = "test_rzp_secret"
WEBHOOK_SECRET = "test-webhook-secret-value"


@pytest.fixture(autouse=True)
def _payment_and_webhook_secrets(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_key_secret", RZP_SECRET)
    monkeypatch.setattr(settings, "agent_webhook_secret", WEBHOOK_SECRET)
    yield
    app.dependency_overrides.pop(get_current_actor, None)


async def _make_actor(db_session, name="Owner", roles=None) -> Actor:
    actor = Actor(
        id=uuid.uuid4(),
        type=ActorType.HUMAN,
        name=name,
        email=f"{uuid.uuid4().hex[:8]}@example.test",
        roles=roles or [Role.INITIATOR],
        permissions=[],
    )
    db_session.add(actor)
    await db_session.commit()
    await db_session.refresh(actor)
    return actor


def _act_as(actor: Actor) -> None:
    async def _override():
        return actor

    app.dependency_overrides[get_current_actor] = _override


def _sign(order_id: str, payment_id: str) -> str:
    return hmac.new(RZP_SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


async def _pay(client: AsyncClient, body: dict) -> dict:
    """Create a server-priced order and complete it the way Razorpay Checkout would."""
    order = await client.post("/onboarding/wallet/create-order", json=body)
    assert order.status_code == 200, order.text
    o = order.json()
    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    ok = await client.post(
        "/onboarding/wallet/verify-payment",
        json={
            "razorpay_order_id": o["order_id"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": _sign(o["order_id"], payment_id),
        },
    )
    assert ok.status_code == 200, ok.text
    return {"order": o, "payment_id": payment_id, "wallet": ok.json()}


@pytest_asyncio.fixture
async def owner(db_session):
    actor = await _make_actor(db_session, "Owner")
    _act_as(actor)
    return actor


# ------------------------------------------------------------------ pricing math
def test_every_plan_is_exactly_60_40_and_gst_is_on_top():
    for plan in pricing.PLANS.values():
        s = pricing.split_plan(plan)
        assert s.platform_profit_paise + s.provider_pool_paise == s.base_paise
        assert s.platform_profit_paise == s.base_paise * 60 // 100
        assert s.total_paise == s.base_paise + s.gst_paise
        assert s.gst_paise == round(s.base_paise * 0.18)
        # the customer-credited minutes never cost more than the call pool
        assert s.included_minutes * pricing.RAW_COST_PER_MIN_PAISE <= s.call_pool_paise


def test_known_plan_numbers():
    personal = pricing.split_plan(pricing.PLANS["personal"])
    assert personal.total_paise == 117_882  # 999 + 18% GST
    assert personal.platform_profit_paise == 59_940
    assert personal.call_pool_paise == 34_060  # 399.60 pool minus Rs. 59 DID
    assert personal.included_minutes == 113
    pilot = pricing.split_plan(pricing.PLANS["pilot"])
    assert pilot.wallet_credit_paise == 65_150  # 260.60 call pool at 2.5x retail


def test_call_debit_rounds_up_and_never_zero():
    assert pricing.call_debit_paise(60) == 750
    assert pricing.call_debit_paise(1) == 13  # 12.5 paise rounds up
    assert pricing.call_debit_paise(0) == 13


# ------------------------------------------------------------------- public API
@pytest.mark.asyncio
async def test_plans_are_public(client: AsyncClient):
    r = await client.get("/onboarding/plans")
    assert r.status_code == 200
    assert r.json()["gst_pct"] == 18
    prices = {p["plan_id"]: p["price_inr"] for p in r.json()["plans"]}
    assert prices == {"pilot": 799.0, "personal": 999.0, "vyapar": 2499.0, "udyog": 4999.0, "enterprise": 11999.0}


@pytest.mark.asyncio
async def test_old_free_credit_and_public_metering_routes_are_gone(client: AsyncClient, owner):
    for path in ("/onboarding/activate-starter-499", "/onboarding/wallet/activate-starter-499",
                 "/onboarding/topup-wallet", "/onboarding/wallet/topup", "/onboarding/meter-call"):
        r = await client.post(path, json={"tenant_id": "x", "amount_inr": 500, "duration_seconds": 5})
        assert r.status_code in (404, 405), path


@pytest.mark.asyncio
async def test_wallet_routes_need_login(client: AsyncClient):
    assert (await client.get("/onboarding/wallet/me")).status_code in (401, 403)
    assert (await client.post("/onboarding/wallet/create-order", json={"plan_id": "vyapar"})).status_code in (401, 403)


# ------------------------------------------------------------------ buying a plan
@pytest.mark.asyncio
async def test_buy_plan_activates_wallet_with_server_price_and_gst_invoice(client: AsyncClient, owner):
    paid = await _pay(client, {"plan_id": "vyapar", "business_name": "Tumkur Ceramics", "mascot_id": "v2",
                               "gstin": "29AABCT0000A1Z5"})
    assert paid["order"]["amount_payable_inr"] == 2948.82
    assert paid["order"]["price_inr"] == 2499.0
    w = paid["wallet"]
    assert w["deployment_status"] == "ACTIVE"
    assert w["plan_id"] == "vyapar"
    assert w["mascot_id"] == "v2"
    assert w["plan_valid_until"] is not None
    expected_credit = pricing.split_plan(pricing.PLANS["vyapar"]).wallet_credit_paise / 100
    assert w["call_balance_inr"] == expected_credit
    assert w["total_paid_incl_gst_inr"] == 2948.82

    inv = await client.get(f"/onboarding/gst-invoice/{owner.id}")
    assert inv.status_code == 200
    invoice = inv.json()["invoices"][0]
    assert invoice["sac_code"] == "998315"
    assert invoice["customer_gstin"] == "29AABCT0000A1Z5"
    assert invoice["supply_type"] == "INTRA_STATE_CGST_SGST"
    assert invoice["taxable_amount_inr"] == 2499.0
    assert invoice["cgst_9_pct_inr"] + invoice["sgst_9_pct_inr"] == 449.82
    assert invoice["total_gross_inr"] == 2948.82
    assert invoice["invoice_number"].startswith("SGM/")


@pytest.mark.asyncio
async def test_inter_state_gstin_gets_igst(client: AsyncClient, owner):
    await _pay(client, {"plan_id": "personal", "gstin": "33AABCM1234A1Z5"})
    inv = (await client.get(f"/onboarding/gst-invoice/{owner.id}")).json()["invoices"][0]
    assert inv["supply_type"] == "INTER_STATE_IGST"
    assert inv["igst_18_pct_inr"] == 179.82
    assert inv["cgst_9_pct_inr"] == 0.0


@pytest.mark.asyncio
async def test_same_payment_cannot_credit_twice(client: AsyncClient, owner):
    paid = await _pay(client, {"plan_id": "personal"})
    balance = paid["wallet"]["call_balance_inr"]
    again = await client.post(
        "/onboarding/wallet/verify-payment",
        json={
            "razorpay_order_id": paid["order"]["order_id"],
            "razorpay_payment_id": paid["payment_id"],
            "razorpay_signature": _sign(paid["order"]["order_id"], paid["payment_id"]),
        },
    )
    assert again.status_code == 200
    assert again.json().get("idempotent_replay") is True
    assert again.json()["call_balance_inr"] == balance


@pytest.mark.asyncio
async def test_forged_signature_credits_nothing(client: AsyncClient, owner):
    order = (await client.post("/onboarding/wallet/create-order", json={"plan_id": "udyog"})).json()
    r = await client.post(
        "/onboarding/wallet/verify-payment",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": "pay_forged00001",
              "razorpay_signature": "0" * 64},
    )
    assert r.status_code == 400
    w = (await client.get("/onboarding/wallet/me")).json()
    assert w["call_balance_inr"] == 0.0
    assert w["deployment_status"] == "UNPROVISIONED"


@pytest.mark.asyncio
async def test_cannot_verify_someone_elses_order(client: AsyncClient, db_session, owner):
    order = (await client.post("/onboarding/wallet/create-order", json={"plan_id": "personal"})).json()
    mallory = await _make_actor(db_session, "Mallory")
    _act_as(mallory)
    pid = "pay_stolen000001"
    r = await client.post(
        "/onboarding/wallet/verify-payment",
        json={"razorpay_order_id": order["order_id"], "razorpay_payment_id": pid,
              "razorpay_signature": _sign(order["order_id"], pid)},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_order_validation(client: AsyncClient, owner):
    assert (await client.post("/onboarding/wallet/create-order", json={"plan_id": "free-forever"})).status_code == 422
    assert (await client.post("/onboarding/wallet/create-order", json={})).status_code == 422
    both = {"plan_id": "personal", "topup_amount_inr": 500}
    assert (await client.post("/onboarding/wallet/create-order", json=both)).status_code == 422
    assert (await client.post("/onboarding/wallet/create-order", json={"topup_amount_inr": 5})).status_code == 422
    assert (await client.post("/onboarding/wallet/create-order", json={"topup_amount_inr": 9_999_999})).status_code == 422
    # a client-sent price is simply ignored
    r = await client.post("/onboarding/wallet/create-order", json={"plan_id": "enterprise", "amount_inr": 1})
    assert r.status_code == 200
    assert r.json()["price_inr"] == 11999.0


# ---------------------------------------------------------------------- top-ups
@pytest.mark.asyncio
async def test_topup_needs_a_plan_then_credits_base_and_locks_60_percent(client: AsyncClient, owner):
    blocked = await client.post("/onboarding/wallet/create-order", json={"topup_amount_inr": 500})
    assert blocked.status_code == 409

    first = await _pay(client, {"plan_id": "personal"})
    before = first["wallet"]
    paid = await _pay(client, {"topup_amount_inr": 500})
    assert paid["order"]["amount_payable_inr"] == 590.0
    after = paid["wallet"]
    assert round(after["call_balance_inr"] - before["call_balance_inr"], 2) == 500.0
    assert round(after["total_paid_incl_gst_inr"] - before["total_paid_incl_gst_inr"], 2) == 590.0


# ------------------------------------------------------------------- isolation
@pytest.mark.asyncio
async def test_other_users_cannot_read_or_use_my_tenant(client: AsyncClient, db_session, owner):
    await _pay(client, {"plan_id": "personal"})
    mallory = await _make_actor(db_session, "Mallory")
    _act_as(mallory)
    for method, path, body in (
        ("get", f"/onboarding/wallet/{owner.id}", None),
        ("get", f"/onboarding/gst-invoice/{owner.id}", None),
        ("get", f"/onboarding/composio/{owner.id}", None),
        ("get", f"/onboarding/viral-kit/{owner.id}", None),
        ("delete", f"/onboarding/delete-account/{owner.id}", None),
        ("post", "/onboarding/wallet/create-order", {"plan_id": "personal", "tenant_id": str(owner.id)}),
        ("post", "/onboarding/composio/connect", {"tenant_id": str(owner.id), "app_name": "WHATSAPP"}),
        ("post", "/onboarding/wallet/autopay", {"tenant_id": str(owner.id), "enabled": True}),
    ):
        r = await getattr(client, method)(path, **({"json": body} if body else {}))
        assert r.status_code == 404, (method, path, r.status_code)
    # and the owner's wallet is untouched
    _act_as(owner)
    assert (await client.get("/onboarding/wallet/me")).json()["plan_id"] == "personal"


@pytest.mark.asyncio
async def test_seeded_pilot_tenants_are_not_claimable(client: AsyncClient, db_session, owner):
    await seed_live_tenants(db_session)
    r = await client.get("/onboarding/wallet/abhishek-industries")
    assert r.status_code == 404
    r = await client.post("/onboarding/wallet/create-order", json={"plan_id": "personal", "tenant_id": "abhishek-industries"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_see_seeded_tenant_and_economics(client: AsyncClient, db_session, owner):
    await seed_live_tenants(db_session)
    await _pay(client, {"plan_id": "vyapar"})
    assert (await client.get("/onboarding/admin/economics")).status_code == 403

    admin = await _make_actor(db_session, "Founder", roles=[Role.ADMIN])
    _act_as(admin)
    w = await client.get("/onboarding/wallet/abhishek-industries")
    assert w.status_code == 200
    assert w.json()["assigned_did"] == "+918064270314"
    econ = (await client.get("/onboarding/admin/economics")).json()
    assert econ["total_platform_net_profit_inr"] > 0
    assert econ["total_tenants"] >= 3


# --------------------------------------------------------------------- metering
def _webhook():
    return {"X-Webhook-Secret": WEBHOOK_SECRET}


@pytest.mark.asyncio
async def test_call_metering_is_idempotent_and_pauses_at_zero(client: AsyncClient, owner):
    paid = await _pay(client, {"plan_id": "pilot"})
    tid = str(owner.id)
    start = paid["wallet"]["call_balance_inr"]

    body = {"call_id": "call-A", "tenant_id": tid, "duration_seconds": 60}
    meter_headers = {**_webhook(), "X-Tenant-Key": paid["wallet"]["metering_key"]}
    r1 = await client.post("/agent-callbacks/call-ended", json=body, headers=meter_headers)
    assert r1.status_code == 200
    assert r1.json()["debited_inr"] == 7.5
    assert r1.json()["remaining_balance_inr"] == round(start - 7.5, 2)

    r2 = await client.post("/agent-callbacks/call-ended", json=body, headers=meter_headers)
    assert r2.json()["remaining_balance_inr"] == r1.json()["remaining_balance_inr"]  # no double debit

    huge = {"call_id": "call-B", "tenant_id": tid, "duration_seconds": 36_000}
    r3 = await client.post("/agent-callbacks/call-ended", json=huge, headers=meter_headers)
    assert r3.json()["remaining_balance_inr"] == 0.0  # never negative
    assert r3.json()["circuit_breaker_triggered"] is True
    w = (await client.get("/onboarding/wallet/me")).json()
    assert w["deployment_status"] == "PAUSED_ZERO_BALANCE"

    top = await _pay(client, {"topup_amount_inr": 200})
    assert top["wallet"]["deployment_status"] == "ACTIVE"
    assert top["wallet"]["call_balance_inr"] == 200.0


@pytest.mark.asyncio
async def test_metering_webhook_rejects_missing_or_wrong_secret(client: AsyncClient, owner):
    body = {"call_id": "call-C", "tenant_id": str(owner.id), "duration_seconds": 30}
    assert (await client.post("/agent-callbacks/call-ended", json=body)).status_code == 401
    bad = await client.post("/agent-callbacks/call-ended", json=body, headers={"X-Webhook-Secret": "nope"})
    assert bad.status_code == 401


# ---------------------------------------------------------------------- referral
@pytest.mark.asyncio
async def test_referral_once_only_after_paying_and_never_your_own_code(client: AsyncClient, db_session, owner):
    alice_wallet = (await _pay(client, {"plan_id": "personal"}))["wallet"]
    alice_code = alice_wallet["referral_code"]

    bob = await _make_actor(db_session, "Bob")
    _act_as(bob)
    early = await client.post("/onboarding/wallet/referral", json={"referral_code": alice_code})
    assert early.status_code == 409  # has not paid yet

    await _pay(client, {"plan_id": "personal"})
    bob_balance = (await client.get("/onboarding/wallet/me")).json()["call_balance_inr"]
    ok = await client.post("/onboarding/wallet/referral", json={"referral_code": alice_code})
    assert ok.status_code == 200
    assert ok.json()["bonus_credited_inr"] == 100.0
    assert ok.json()["new_tenant_balance_inr"] == round(bob_balance + 100, 2)

    again = await client.post("/onboarding/wallet/referral", json={"referral_code": alice_code})
    assert again.status_code == 409

    own_code = (await client.get("/onboarding/wallet/me")).json()["referral_code"]
    carol = await _make_actor(db_session, "Carol")
    _act_as(carol)
    await _pay(client, {"plan_id": "personal"})
    own = (await client.get("/onboarding/wallet/me")).json()["referral_code"]
    self_use = await client.post("/onboarding/wallet/referral", json={"referral_code": own})
    assert self_use.status_code == 404
    assert own_code != own

    _act_as(owner)
    alice_after = (await client.get("/onboarding/wallet/me")).json()
    assert alice_after["call_balance_inr"] == round(alice_wallet["call_balance_inr"] + 100, 2)


# ---------------------------------------------------------- tools, autopay, delete
@pytest.mark.asyncio
async def test_tool_connections_persist_and_are_honestly_simulated(client: AsyncClient, owner):
    r = await client.post(
        "/onboarding/composio/connect",
        json={"app_name": "ZOHO_CRM", "metadata": {"org": "Acme", "api_token": "super-secret"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["live"] is False
    assert body["status"] == "SIMULATED_CONNECTED"
    assert "api_token" not in body["connection"]

    listing = (await client.get("/onboarding/composio/tools")).json()
    zoho = next(t for t in listing["tools"] if t["app"] == "ZOHO_CRM")
    assert zoho["connected"] is True and zoho["live"] is False

    ex = (await client.post(
        "/onboarding/composio/execute",
        json={"caller_name": "Ravi", "caller_phone": "+919845098450", "requirement_summary": "25 tonnes clay"},
    )).json()
    assert ex["live"] is False
    assert ex["executed_count"] == 1
    assert ex["executions"][0]["status"] == "SIMULATED"

    gone = await client.delete(f"/onboarding/composio/connect/{owner.id}/ZOHO_CRM")
    assert gone.json()["status"] == "DISCONNECTED"


@pytest.mark.asyncio
async def test_autopay_is_only_a_preference_and_creates_no_money(client: AsyncClient, owner):
    paid = await _pay(client, {"plan_id": "personal"})
    r = await client.post("/onboarding/wallet/autopay", json={"enabled": True, "threshold_inr": 100, "autopay_amount_inr": 299})
    assert r.status_code == 200
    assert r.json()["upi_autopay_enabled"] is True
    assert r.json()["mandate_status"] == "NOT_CONNECTED"
    assert r.json()["call_balance_inr"] == paid["wallet"]["call_balance_inr"]

    # draining the wallet below the threshold must not conjure a top-up
    drain = await client.post(
        "/agent-callbacks/call-ended",
        json={"call_id": "call-D", "tenant_id": str(owner.id), "duration_seconds": 36_000},
        headers={**_webhook(), "X-Tenant-Key": paid["wallet"]["metering_key"]},
    )
    assert drain.json()["remaining_balance_inr"] == 0.0

    bad = await client.post("/onboarding/wallet/autopay", json={"enabled": True, "threshold_inr": 5, "autopay_amount_inr": 1})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_report_and_delete_account_keep_ledger_but_erase_identity(client: AsyncClient, owner):
    await _pay(client, {"plan_id": "personal", "business_name": "Secret Sweets", "gstin": "29AABCS0000A1Z5"})
    await client.post("/onboarding/composio/connect", json={"app_name": "WHATSAPP"})

    rep = await client.post("/onboarding/report-ai-output", json={"call_id": "c1", "utterance_flagged": "rude reply"})
    assert rep.status_code == 201
    assert rep.json()["status"] == "LOGGED_FOR_GUARDRAIL_REVIEW"

    dele = await client.delete(f"/onboarding/delete-account/{owner.id}")
    assert dele.status_code == 200
    assert dele.json()["status"] == "DELETED"
    assert "tool_connections" in dele.json()["deleted_items"]

    w = (await client.get("/onboarding/wallet/me")).json()
    assert w["business_name"] != "Secret Sweets"
    assert w["gstin"] is None
    assert w["call_balance_inr"] == 0.0
    # GST records survive, anonymised
    inv = (await client.get(f"/onboarding/gst-invoice/{owner.id}")).json()
    assert inv["count"] == 1
    assert inv["invoices"][0]["customer_name"] == "Deleted account"


# -------------------------------------------------------------------- plan expiry
@pytest.mark.asyncio
async def test_expired_plan_pauses_line_and_topup_does_not_revive_it(client: AsyncClient, db_session, owner):
    from datetime import timedelta

    from app.core.billing_service import BillingService, _now

    await _pay(client, {"plan_id": "personal"})
    wallet = await BillingService(db_session).get_wallet(str(owner.id))
    wallet.plan_valid_until = _now() - timedelta(days=1)
    await db_session.commit()

    w = (await client.get("/onboarding/wallet/me")).json()
    assert w["deployment_status"] == "PLAN_EXPIRED"
    top = await _pay(client, {"topup_amount_inr": 500})
    assert top["wallet"]["deployment_status"] == "PLAN_EXPIRED"

    renewed = await _pay(client, {"plan_id": "personal"})
    assert renewed["wallet"]["deployment_status"] == "ACTIVE"


# ---------------------------------------------------------------------- other
@pytest.mark.asyncio
async def test_sim_forwarding_codes_and_privacy_policy_are_public(client: AsyncClient):
    sim = await client.get("/onboarding/sim-forwarding-codes?virtual_number=+918064270314")
    assert sim.status_code == 200
    modes = sim.json()["modes"]
    assert modes["when_busy"]["activate_ussd"] == "*67*08064270314#"
    assert modes["reset_all"]["deactivate_ussd"] == "##002#"
    priv = await client.get("/onboarding/privacy-policy")
    assert "DPDP" in priv.text
