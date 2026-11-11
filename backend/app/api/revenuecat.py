"""RevenueCat webhook: Google Play purchases credit the buyer's wallet.

The Android app sells plans and top-ups through Google Play Billing, with
RevenueCat validating each purchase against Google. RevenueCat then posts an
event here. The app identifies the buyer to RevenueCat with their Sangam actor
id (``Purchases.logIn(actorId)``), so ``app_user_id`` names the actor whose
wallet is credited.

Authentication is the shared ``Authorization`` header configured in the
RevenueCat dashboard (Project -> Integrations -> Webhooks). The client app is
never trusted to report a purchase.

Play product ids map to Sangam pricing:

* Subscriptions named after a plan id (``personal``, ``vyapar``, ``udyog``,
  ``enterprise``). RevenueCat reports them as ``<plan>:<base plan>``.
* One-time product ``pilot`` for the 7-day pilot.
* Consumable ``topup_<rupees>`` (for example ``topup_500``) for call credit.

Credits are idempotent on the store transaction id, so RevenueCat's retries
and duplicate deliveries never credit twice.

Refunds: RevenueCat reports a Play refund as ``CANCELLATION`` with
``cancel_reason`` ``CUSTOMER_SUPPORT`` (or a ``REFUND`` event). The credit that
purchase added is taken back, never below zero, so a refund cannot leave the
buyer with free calls. ``REFUND_REVERSED`` is logged for a person to review.
"""
from __future__ import annotations

import hmac
import logging
import re
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core import pricing
from app.core.billing_service import BillingError, BillingService
from app.db.session import get_session
from app.models.actor import Actor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/revenuecat", tags=["billing"])

# Events that mean money changed hands for a new period or a one-time product.
_CREDIT_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "NON_RENEWING_PURCHASE"}
# Events that change nothing in the wallet: the paid-through date already
# stands, and Play handles cancellation, billing retry and refunds.
# CANCELLATION with these reasons means the money went back to the buyer.
_REFUND_CANCEL_REASONS = {"CUSTOMER_SUPPORT", "REFUND"}
_NOOP_EVENTS = {
    "TEST",
    "UNCANCELLATION",
    "EXPIRATION",
    "BILLING_ISSUE",
    "PRODUCT_CHANGE",
    "SUBSCRIPTION_PAUSED",
    "SUBSCRIPTION_EXTENDED",
    "TRANSFER",
    "TEMPORARY_ENTITLEMENT_GRANT",
    "INVOICE_ISSUANCE",
    "SUBSCRIBER_ALIAS",
    "VIRTUAL_CURRENCY_TRANSACTION",
}
_TOPUP_RE = re.compile(r"^topup_(\d{2,6})$")
_MAX_TOPUP_INR = 100_000


def _authorized(header_value: Optional[str]) -> bool:
    expected = (settings.revenuecat_webhook_auth or "").strip()
    if not expected:
        return False
    supplied = (header_value or "").strip()
    if supplied.lower().startswith("bearer "):
        supplied = supplied[7:].strip()
    if expected.lower().startswith("bearer "):
        expected = expected[7:].strip()
    return hmac.compare_digest(supplied.encode(), expected.encode())


def _base_product_id(product_id: str) -> str:
    # Play subscriptions arrive as "<subscription id>:<base plan id>".
    return (product_id or "").split(":", 1)[0].strip().lower()


async def _actor_for(session: AsyncSession, app_user_id: str) -> Optional[Actor]:
    try:
        actor_id = uuid.UUID(app_user_id)
    except (TypeError, ValueError):
        return None
    actor = await session.get(Actor, actor_id)
    if actor is None or not actor.is_active:
        return None
    return actor


@router.post("/webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON")
    event = body.get("event") if isinstance(body, dict) else None
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Missing event")

    event_type = str(event.get("type") or "")
    event_id = str(event.get("id") or "")
    cancel_reason = str(event.get("cancel_reason") or "").upper()
    is_refund = event_type == "REFUND" or (
        event_type == "CANCELLATION" and cancel_reason in _REFUND_CANCEL_REASONS
    )
    if event_type == "CANCELLATION" and not is_refund:
        # A plain cancellation stops renewal; the paid-through period stands.
        return {"status": "ignored", "type": event_type}
    if event_type == "REFUND_REVERSED":
        logger.error("revenuecat refund reversed; review the wallet by hand", extra={"event_id": event_id})
        return {"status": "ignored", "type": event_type, "reason": "refund reversals are reviewed by hand"}
    if event_type in _NOOP_EVENTS:
        logger.info("revenuecat event ignored", extra={"type": event_type, "event_id": event_id})
        return {"status": "ignored", "type": event_type}
    if event_type not in _CREDIT_EVENTS and not is_refund:
        logger.warning("revenuecat event type not handled", extra={"type": event_type, "event_id": event_id})
        return {"status": "ignored", "type": event_type}

    environment = str(event.get("environment") or "PRODUCTION").upper()
    if environment == "SANDBOX" and not settings.revenuecat_accept_sandbox:
        return {"status": "ignored", "reason": "sandbox purchases are not credited on this server"}

    store = str(event.get("store") or "")
    if store and store != "PLAY_STORE":
        # Only Google Play is sold through RevenueCat today.
        return {"status": "ignored", "reason": f"store {store} is not handled"}

    transaction_id = str(event.get("transaction_id") or "").strip()
    product_id = _base_product_id(str(event.get("product_id") or ""))
    app_user_id = str(event.get("app_user_id") or "").strip()
    if not transaction_id or not product_id or not app_user_id:
        raise HTTPException(status_code=400, detail="Event is missing transaction, product or user")

    actor = await _actor_for(session, app_user_id)
    if actor is None:
        # Anonymous RevenueCat ids ($RCAnonymousID:...) or deleted accounts.
        # 200 so RevenueCat stops retrying; the purchase stays visible there.
        logger.error(
            "revenuecat purchase for unknown user",
            extra={"event_id": event_id, "app_user_id": app_user_id, "product_id": product_id},
        )
        return {"status": "ignored", "reason": "unknown app_user_id"}

    tenant_id = str(actor.id)
    payment_id = f"play:{transaction_id}"
    svc = BillingService(session)
    if is_refund:
        try:
            reversal = await svc.reverse_payment(tenant_id, payment_id, f"play-refund:{transaction_id}")
            await session.commit()
        except BillingError as exc:
            await session.rollback()
            raise HTTPException(status_code=exc.status_code, detail=exc.detail)
        if reversal.get("status") == "not_found":
            logger.error("revenuecat refund for a purchase never credited", extra={"event_id": event_id})
        return {
            "status": reversal.get("status"),
            "tenant_id": tenant_id,
            "product_id": product_id,
            "reversed_inr": reversal.get("reversed_paise", 0) / 100,
            "environment": environment,
        }
    try:
        plan = pricing.get_plan(product_id)
        topup = _TOPUP_RE.match(product_id)
        if plan is not None:
            result = await svc.credit_plan(tenant_id, plan, payment_id, owner_actor_id=actor.id)
        elif topup is not None and 0 < int(topup.group(1)) <= _MAX_TOPUP_INR:
            await svc.get_or_create_wallet(tenant_id, owner_actor_id=actor.id)
            result = await svc.credit_topup(tenant_id, int(topup.group(1)) * 100, payment_id)
        else:
            logger.error("revenuecat product not mapped", extra={"event_id": event_id, "product_id": product_id})
            return {"status": "ignored", "reason": f"product {product_id} is not mapped to a plan or top-up"}
        await session.commit()
    except BillingError as exc:
        await session.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return {
        "status": "credited" if not result.get("idempotent_replay") else "already_credited",
        "tenant_id": tenant_id,
        "product_id": product_id,
        "environment": environment,
    }
