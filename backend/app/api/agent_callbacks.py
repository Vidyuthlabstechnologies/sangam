"""Callback requests captured by the Sarvam voice agent.

POST is a webhook: the agent platform calls it, so it cannot use a user login.
It is authenticated by a shared secret in X-Webhook-Secret, and that secret
only ever grants WRITE access. Reading and updating the list needs a normal
logged-in actor.

Nothing that looks like an Aadhaar or PAN number is stored: phone numbers that could
be one are refused, and 12-digit Aadhaar or 10-char PAN runs in free text are masked.
"""
import hmac
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.api.onboarding import _is_admin, owned_tenant_ids
from app.config import settings
from app.core.agent_forwarders import forward_callback
from app.core import composio_router
from app.core.billing_service import BillingService
from app.db.session import get_session
from app.models.actor import Actor
from app.models.sangamitra_release import TenantWalletModel
from app.models.voice_callback import CallbackStatus, VoiceCallback

# Two routers on purpose. webhook_router is the ONLY thing the public tunnel
# app mounts (app/webhook_app.py); the staff routes need a login and stay on
# the full API, so they are never reachable from the public internet.
webhook_router = APIRouter(prefix="/agent-callbacks", tags=["agent-callbacks"])
router = APIRouter(prefix="/agent-callbacks", tags=["agent-callbacks"])

logger = logging.getLogger("sangam.agent_callbacks")

SERVICES = {
    # Citizen Services (Surya Enterprises)
    "aadhaar", "pan", "banking_financial", "utility_bills", "travel_tickets",
    "epfo_pf", "meeseva_govt", "passport_id", "not_offered", "unclear",
    # B2B Industrial & Minerals (Abhishek Industries)
    "kaolin", "china_clay", "quartz", "silica", "feldspar", "dolomite",
    "bentonite", "soapstone", "mineral_inquiry", "bulk_order", "sample_request",
    # All-India Vertical Packs
    "clinic_appointment", "lab_test", "site_visit", "property_inquiry",
    "table_booking", "catering_order", "salon_slot", "auto_service",
    "course_admission", "tax_gst_filing", "hotel_room", "astrology_slot",
    "logistics_quote", "hardware_wholesale", "jewellery_inquiry",
    "order_tracking", "event_booking", "gym_membership", "vet_appointment",
    "solar_survey", "personal_screen", "rwa_helpdesk", "cab_rental", "appliance_repair",
}
_AADHAAR_LIKE = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
_PAN_LIKE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def _mask(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    masked = _AADHAAR_LIKE.sub("[redacted]", value)
    masked = _PAN_LIKE.sub("[redacted-pan]", masked)
    return masked.strip()[:limit] or None


def _normalise_phone(raw: str) -> str:
    """Indian mobile to +91XXXXXXXXXX, or ValueError.

    A bare 12-digit number is only accepted when it is 91 followed by a mobile
    number; anything else could be an Aadhaar number and is refused.
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return "+" + digits
    raise ValueError("caller_phone must be an Indian mobile number")


class CallbackIn(BaseModel):
    caller_name: Optional[str] = Field(default=None, max_length=200)
    caller_phone: str
    service: str = "unclear"
    preferred_time: Optional[str] = Field(default=None, max_length=200)
    language: Optional[str] = Field(default=None, max_length=32)
    urgency: str = "normal"
    notes: Optional[str] = Field(default=None, max_length=1000)
    call_id: Optional[str] = Field(default=None, max_length=64)
    tenant_id: Optional[str] = Field(default=None, max_length=100)
    duration_seconds: Optional[int] = Field(default=0, ge=0)
    recording_url: Optional[str] = Field(default=None, max_length=500)
    ai_summary: Optional[str] = Field(default=None, max_length=1000)
    items_json: Optional[List[Dict[str, Any]]] = None

    @field_validator("caller_phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return _normalise_phone(v)

    @field_validator("urgency")
    @classmethod
    def _urgency(cls, v: str) -> str:
        if v not in ("normal", "urgent"):
            raise ValueError("urgency must be normal or urgent")
        return v

    @field_validator("service")
    @classmethod
    def _service(cls, v: str) -> str:
        v = (v or "").strip().lower()
        return v if v in SERVICES else "unclear"


class CallEndedWebhookIn(BaseModel):
    call_id: str = Field(..., max_length=64)
    tenant_id: str = Field(..., max_length=100)
    caller_phone: Optional[str] = None
    duration_seconds: int = Field(..., ge=1)
    language: str = "kn-IN"
    recording_url: Optional[str] = None
    summary: Optional[str] = None


class StatusIn(BaseModel):
    status: CallbackStatus


def _view(row: VoiceCallback) -> dict:
    return {
        "id": str(row.id),
        "call_id": row.call_id,
        "tenant_id": row.tenant_id,
        "caller_name": row.caller_name,
        "caller_phone": row.caller_phone,
        "service": row.service,
        "preferred_time": row.preferred_time,
        "language": row.language,
        "urgency": row.urgency,
        "notes": row.notes,
        "duration_seconds": row.duration_seconds or 0,
        "recording_url": row.recording_url,
        "ai_summary": row.ai_summary,
        "items_json": row.items_json,
        "status": row.status.value,
        "created_at": row.created_at.isoformat(),
    }


async def prove_tenant(session: AsyncSession, tenant_id: Optional[str], tenant_key: Optional[str]) -> Optional[str]:
    """The shared webhook secret is not enough to name a wallet.

    The body tenant is accepted only when it matches the server-stored
    per-tenant metering key. Anything else is unattached and is not debited.
    """
    if not tenant_id or not tenant_key:
        return None
    wallet = await BillingService(session).get_wallet(tenant_id)
    if wallet is None or not wallet.metering_key:
        return None
    try:
        ok = hmac.compare_digest(tenant_key.encode(), wallet.metering_key.encode())
    except Exception:
        return None
    return wallet.tenant_id if ok else None


async def require_webhook_secret(
    x_webhook_secret: Optional[str] = Header(default=None),
) -> None:
    expected = settings.agent_webhook_secret
    if not expected or not x_webhook_secret:
        # Unset secret fails closed: a missing setting must never mean open.
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    if not hmac.compare_digest(x_webhook_secret.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@webhook_router.post("", status_code=201, response_model=dict)
async def record_callback(
    body: CallbackIn,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_webhook_secret),
    x_tenant_key: Optional[str] = Header(default=None),
):
    if body.call_id:
        existing = (
            await session.execute(select(VoiceCallback).where(VoiceCallback.call_id == body.call_id))
        ).scalar_one_or_none()
        if existing is not None:
            # The platform retried; return the original instead of duplicating.
            response.status_code = 200
            return {"id": str(existing.id), "status": "duplicate"}

    proven_tenant = await prove_tenant(session, body.tenant_id, x_tenant_key)
    row = VoiceCallback(
        call_id=body.call_id,
        tenant_id=proven_tenant,
        caller_name=_mask(body.caller_name, 100),
        caller_phone=body.caller_phone,
        service=body.service,
        preferred_time=_mask(body.preferred_time, 100),
        language=_mask(body.language, 16),
        urgency=body.urgency,
        notes=_mask(body.notes, 1000),
        duration_seconds=body.duration_seconds or 0,
        recording_url=body.recording_url,
        ai_summary=_mask(body.ai_summary, 1000),
        items_json=body.items_json,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    # Snapshot now: a rollback below would expire the ORM row.
    view = _view(row)
    row_id = row.id
    notes = row.notes or ""
    # Billing and tool logging must never fail the webhook: the callback row is already saved.
    try:
        if proven_tenant:
            if body.duration_seconds and body.duration_seconds > 0:
                await BillingService(session).meter_call(proven_tenant, body.duration_seconds, body.call_id)
            await composio_router.execute_post_call_chain(
                session,
                tenant_id=proven_tenant,
                caller_name=view["caller_name"] or "Caller",
                caller_phone=view["caller_phone"] or "",
                requirement_summary=f"{view['service']} - {notes}".strip(" -"),
                language=view["language"] or "kn-IN",
                preferred_time=view["preferred_time"],
            )
            await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Post-callback billing/tool step failed for callback %s", row_id)

    # After the response is sent: forwarding must never delay or fail the call.
    background_tasks.add_task(forward_callback, view)
    logger.info("Recorded voice callback %s (service=%s, urgency=%s)", row_id, view["service"], view["urgency"])
    return {"id": str(row_id), "status": "recorded"}


@webhook_router.post("/call-ended", status_code=200, response_model=dict)
async def handle_call_ended_webhook(
    body: CallEndedWebhookIn,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_webhook_secret),
    x_tenant_key: Optional[str] = Header(default=None),
):
    """Meter a finished call only against the tenant the server can prove."""
    proven = await prove_tenant(session, body.tenant_id, x_tenant_key)
    if proven is None:
        raise HTTPException(status_code=403, detail="Tenant is not bound to this webhook")
    existing = (
        await session.execute(select(VoiceCallback).where(VoiceCallback.call_id == body.call_id))
    ).scalar_one_or_none()
    if existing is not None and existing.tenant_id and existing.tenant_id != proven:
        raise HTTPException(status_code=403, detail="Tenant does not match the recorded call")
    meter_res = await BillingService(session).meter_call(proven, body.duration_seconds, body.call_id)
    await session.commit()
    missed_call_followup = body.duration_seconds <= 15 and bool(body.caller_phone)
    return {
        "call_id": body.call_id,
        "tenant_id": proven,
        "duration_seconds": body.duration_seconds,
        "debited_inr": meter_res.get("last_call_debit_inr", 0.0),
        "remaining_balance_inr": meter_res.get("call_balance_inr", 0.0),
        "circuit_breaker_triggered": meter_res.get("circuit_breaker_triggered", False),
        "missed_call_whatsapp_triggered": missed_call_followup,
    }


async def _owned_tenants(session: AsyncSession, actor: Actor) -> set[str]:
    owned = {str(actor.id)}
    rows = (
        await session.execute(
            select(TenantWalletModel.tenant_id).where(TenantWalletModel.owner_actor_id == actor.id)
        )
    ).scalars().all()
    owned.update(rows)
    return owned


@router.get("", response_model=List[dict])
async def list_callbacks(
    status: Optional[CallbackStatus] = None,
    tenant_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    owned = await _owned_tenants(session, current_actor)
    if tenant_id is not None and tenant_id not in owned:
        raise HTTPException(status_code=404, detail="Callback request not found")
    query = (
        select(VoiceCallback)
        .where(VoiceCallback.tenant_id.in_(owned))
        .order_by(VoiceCallback.created_at.desc())
        .limit(limit)
    )
    if status is not None:
        query = query.where(VoiceCallback.status == status)
    if tenant_id is not None:
        if not _is_admin(current_actor) and tenant_id not in await owned_tenant_ids(session, current_actor):
            raise HTTPException(status_code=404, detail="Business not found")
        query = query.where(VoiceCallback.tenant_id == tenant_id)
    elif not _is_admin(current_actor):
        query = query.where(VoiceCallback.tenant_id.in_(await owned_tenant_ids(session, current_actor)))
    rows = (await session.execute(query)).scalars().all()
    return [_view(r) for r in rows]


@router.patch("/{callback_id}", response_model=dict)
async def update_status(
    callback_id: UUID,
    body: StatusIn,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    row = await session.get(VoiceCallback, callback_id)
    owned = await _owned_tenants(session, current_actor)
    if row is None or row.tenant_id not in owned:
        raise HTTPException(status_code=404, detail="Callback request not found")
    if not _is_admin(current_actor) and (row.tenant_id or "") not in await owned_tenant_ids(session, current_actor):
        raise HTTPException(status_code=404, detail="Callback request not found")
    row.status = body.status
    await session.commit()
    await session.refresh(row)
    return _view(row)
