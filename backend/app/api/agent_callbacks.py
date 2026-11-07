"""Callback requests captured by the Sarvam voice agent.

POST is a webhook: the agent platform calls it, so it cannot use a user login.
It is authenticated by a shared secret in X-Webhook-Secret, and that secret
only ever grants WRITE access. Reading and updating the list needs a normal
logged-in actor.

Nothing that looks like an Aadhaar number is stored: phone numbers that could
be one are refused, and 12-digit runs in free text are masked.
"""
import hmac
import logging
import re
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.config import settings
from app.core.agent_forwarders import forward_callback
from app.db.session import get_session
from app.models.actor import Actor
from app.models.voice_callback import CallbackStatus, VoiceCallback

# Two routers on purpose. webhook_router is the ONLY thing the public tunnel
# app mounts (app/webhook_app.py); the staff routes need a login and stay on
# the full API, so they are never reachable from the public internet.
webhook_router = APIRouter(prefix="/agent-callbacks", tags=["agent-callbacks"])
router = APIRouter(prefix="/agent-callbacks", tags=["agent-callbacks"])

logger = logging.getLogger("sangam.agent_callbacks")

SERVICES = {
    "aadhaar", "pan", "banking_financial", "utility_bills", "travel_tickets",
    "epfo_pf", "meeseva_govt", "passport_id", "not_offered", "unclear",
}
_AADHAAR_LIKE = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")


def _mask(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    return _AADHAAR_LIKE.sub("[redacted]", value).strip()[:limit] or None


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


class StatusIn(BaseModel):
    status: CallbackStatus


def _view(row: VoiceCallback) -> dict:
    return {
        "id": str(row.id),
        "call_id": row.call_id,
        "caller_name": row.caller_name,
        "caller_phone": row.caller_phone,
        "service": row.service,
        "preferred_time": row.preferred_time,
        "language": row.language,
        "urgency": row.urgency,
        "notes": row.notes,
        "status": row.status.value,
        "created_at": row.created_at.isoformat(),
    }


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
):
    if body.call_id:
        existing = (
            await session.execute(select(VoiceCallback).where(VoiceCallback.call_id == body.call_id))
        ).scalar_one_or_none()
        if existing is not None:
            # The platform retried; return the original instead of duplicating.
            response.status_code = 200
            return {"id": str(existing.id), "status": "duplicate"}

    row = VoiceCallback(
        call_id=body.call_id,
        caller_name=_mask(body.caller_name, 100),
        caller_phone=body.caller_phone,
        service=body.service,
        preferred_time=_mask(body.preferred_time, 100),
        language=_mask(body.language, 16),
        urgency=body.urgency,
        notes=_mask(body.notes, 1000),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    # After the response is sent: forwarding must never delay or fail the call.
    background_tasks.add_task(forward_callback, _view(row))
    logger.info("Recorded voice callback %s (service=%s, urgency=%s)", row.id, row.service, row.urgency)
    return {"id": str(row.id), "status": "recorded"}


@router.get("", response_model=List[dict])
async def list_callbacks(
    status: Optional[CallbackStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    query = select(VoiceCallback).order_by(VoiceCallback.created_at.desc()).limit(limit)
    if status is not None:
        query = query.where(VoiceCallback.status == status)
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
    if row is None:
        raise HTTPException(status_code=404, detail="Callback request not found")
    row.status = body.status
    await session.commit()
    await session.refresh(row)
    return _view(row)
