"""The Razorpay webhook is unauthenticated by design — it is called by
Razorpay, not by a logged-in user. Its ONLY authentication is the HMAC
signature over the raw request body. Without that check, anyone who can
reach the endpoint can forge a payment.captured event and mark an
unpaid order as paid.
"""
import hashlib
import hmac
import json
import uuid

import pytest

from app.config import settings
from app.models.payment import Payment, PaymentStatus

WEBHOOK_SECRET = "test_webhook_secret"


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event_body(payment_id: str) -> bytes:
    return json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": payment_id, "order_id": "order_X"}}},
    }).encode()


@pytest.fixture(autouse=True)
def _webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "razorpay_webhook_secret", WEBHOOK_SECRET)


@pytest.mark.asyncio
async def test_unsigned_webhook_rejected(client):
    resp = await client.post(
        "/payments/webhook",
        content=_event_body("pay_1"),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_bad_signature_rejected(client):
    resp = await client.post(
        "/payments/webhook",
        content=_event_body("pay_1"),
        headers={"X-Razorpay-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_signature_from_wrong_secret_rejected(client):
    body = _event_body("pay_1")
    resp = await client.post(
        "/payments/webhook",
        content=body,
        headers={
            "X-Razorpay-Signature": _sign(body, "attacker_guess"),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tampered_body_rejected(client):
    """Signature valid for a different body must not authenticate this one."""
    signed_body = _event_body("pay_original")
    signature = _sign(signed_body)
    tampered = _event_body("pay_attacker")

    resp = await client.post(
        "/payments/webhook",
        content=tampered,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_signature_accepted(client):
    body = _event_body("pay_1")
    resp = await client.post(
        "/payments/webhook",
        content=body,
        headers={"X-Razorpay-Signature": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_forged_capture_does_not_mutate_payment(client, db_session):
    """The security property that actually matters: an unsigned forged
    capture event must not flip a pending payment to CAPTURED."""
    payment = Payment(
        id=uuid.uuid4(),
        amount=500000.0,
        currency="INR",
        status=PaymentStatus.PENDING,
        razorpay_payment_id="pay_victim",
    )
    db_session.add(payment)
    await db_session.commit()

    resp = await client.post(
        "/payments/webhook",
        content=_event_body("pay_victim"),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.PENDING
