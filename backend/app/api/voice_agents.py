"""Sarvam Voice Agents (Samvaad): agents, outbound calls, transcripts and live sessions.

Who may do what:
  * Admins manage the workspace: deployments (agent <-> inbound number),
    interactions across agents, and bindings that grant a business an agent.
  * A business owner can use only the agents bound to their tenant: place an
    outbound call, open a live voice session from the app, and read their own
    calls and transcripts. Both spend minutes, so both need wallet balance, and
    every finished call is metered against the wallet once.

The Voice Agents key never leaves the server. The app opens
``/voice-agents/ws/{app_id}`` here; this process runs the Samvaad SDK session
and relays audio both ways.

Live session protocol (``/voice-agents/ws/{app_id}?token=<Firebase ID token>``):
  client -> server  binary frame   16-bit little-endian PCM, mono, 16 kHz
                    text {"type":"text","text":"..."}   typed user turn
                    text {"type":"end"}                 hang up
  server -> client  text {"type":"ready","interaction_id":...}
                    text {"type":"audio_format","encoding":"pcm_s16le","sample_rate":N}
                         sent before the first agent audio and whenever N changes
                    binary frame   agent audio in that format
                    text {"type":"transcript","role":"user"|"agent","content":...}
                    text {"type":"event","event":"user_interrupt"|...}  stop playback on user_interrupt
                    text {"type":"ended","reason":...,"seconds":N}
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.api.onboarding import _is_admin, resolve_tenant
from app.config import settings
from app.core.billing_service import STATUS_PAUSED_ZERO, BillingService
from app.core.oidc import InvalidAccessToken, link_actor, verify_access_token
from app.core.samvaad import (
    LANGUAGE_NAMES,
    SamvaadClient,
    open_voice_session,
    transcript_from_analytics,
    transcript_from_webhook,
)
from app.db.session import get_session
from app.models.actor import Actor
from app.models.samvaad import (
    SamvaadAgentBinding,
    SamvaadCallAttempt,
    SamvaadCallStatus,
)
from app.models.sangamitra_release import utcnow_naive

logger = logging.getLogger("sangam.voice_agents")

router = APIRouter(prefix="/voice-agents", tags=["voice-agents"])
# Called by Samvaad, not by a user: authenticated by the secret in its URL only.
webhook_router = APIRouter(prefix="/voice-agents/webhooks", tags=["voice-agents"])

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_ID = re.compile(r"^[A-Za-z0-9._:/-]{1,200}$")
_MAX_FRAME_BYTES = 64 * 1024


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _mask_phone(number: str) -> str:
    return number[:3] + "*" * max(len(number) - 7, 0) + number[-4:]


def _require_admin(actor: Actor) -> None:
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Admins only")


async def _binding_for(session: AsyncSession, tenant_id: str, app_id: str) -> SamvaadAgentBinding:
    row = await session.execute(
        select(SamvaadAgentBinding).where(
            SamvaadAgentBinding.tenant_id == tenant_id, SamvaadAgentBinding.app_id == app_id
        )
    )
    binding = row.scalar_one_or_none()
    if binding is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return binding


async def _require_balance(session: AsyncSession, tenant_id: str) -> None:
    wallet = await BillingService(session).get_wallet(tenant_id)
    if wallet is None or wallet.call_balance_paise <= 0 or wallet.deployment_status == STATUS_PAUSED_ZERO:
        raise HTTPException(status_code=402, detail="Add call credit to use voice agents")


def _validate_id(value: str, field: str) -> str:
    value = value.strip()
    if not _ID.match(value):
        raise ValueError(f"{field} has unexpected characters")
    return value


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BindingIn(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=100)
    app_id: str
    app_version: int | None = Field(None, ge=1)
    label: str = Field("", max_length=100)
    connection_id: str | None = None
    agent_phone_number: str | None = None

    @field_validator("app_id")
    @classmethod
    def _app(cls, v: str) -> str:
        return _validate_id(v, "app_id")

    @field_validator("connection_id")
    @classmethod
    def _conn(cls, v: str | None) -> str | None:
        return _validate_id(v, "connection_id") if v else None

    @field_validator("agent_phone_number")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v and not _E164.match(v.strip()):
            raise ValueError("agent_phone_number must be E.164, such as +918047168000")
        return v.strip() if v else None


class BindingOut(BaseModel):
    id: UUID
    tenant_id: str
    app_id: str
    app_version: int | None
    label: str
    agent_phone_number: str | None
    can_call_out: bool


def _binding_out(b: SamvaadAgentBinding) -> BindingOut:
    return BindingOut(
        id=b.id,
        tenant_id=b.tenant_id,
        app_id=b.app_id,
        app_version=b.app_version,
        label=b.label,
        agent_phone_number=b.agent_phone_number,
        can_call_out=bool(b.connection_id and b.agent_phone_number and b.app_version),
    )


class OutboundCallIn(BaseModel):
    app_id: str
    user_phone_number: str
    tenant_id: str | None = None
    agent_variables: dict[str, Any] | None = None
    initial_language_name: str | None = None
    initial_bot_message: str | None = Field(None, max_length=500)

    @field_validator("app_id")
    @classmethod
    def _app(cls, v: str) -> str:
        return _validate_id(v, "app_id")

    @field_validator("user_phone_number")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = re.sub(r"[\s-]", "", v)
        if not _E164.match(v):
            raise ValueError("user_phone_number must be E.164, such as +919876543210")
        return v

    @field_validator("initial_language_name")
    @classmethod
    def _lang(cls, v: str | None) -> str | None:
        if v and v not in LANGUAGE_NAMES:
            raise ValueError(f"initial_language_name must be one of {sorted(LANGUAGE_NAMES)}")
        return v

    @field_validator("agent_variables")
    @classmethod
    def _vars(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and len(json.dumps(v, default=str)) > 8000:
            raise ValueError("agent_variables is too large")
        return v


class CallOut(BaseModel):
    id: UUID
    attempt_id: str | None
    tenant_id: str
    app_id: str
    app_version: int
    user_phone: str
    status: str
    duration_seconds: float | None
    interaction_id: str | None
    failure_reason: str | None
    final_agent_variables: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None


def _call_out(c: SamvaadCallAttempt) -> CallOut:
    return CallOut(
        id=c.id,
        attempt_id=c.attempt_id,
        tenant_id=c.tenant_id,
        app_id=c.app_id,
        app_version=c.app_version,
        user_phone=c.user_phone_masked,
        status=c.status,
        duration_seconds=c.duration_seconds,
        interaction_id=c.interaction_id,
        failure_reason=c.failure_reason,
        final_agent_variables=c.final_agent_variables,
        created_at=c.created_at,
        completed_at=c.completed_at,
    )


class TranscriptOut(BaseModel):
    interaction_id: str | None
    messages: list[dict[str, str]]


class DeploymentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    app_id: str
    app_version: int = Field(..., ge=1)
    connection_configs: list[dict[str, Any]] = Field(..., min_length=1)
    description: str | None = Field(None, max_length=150)
    inbound_config: dict[str, Any] | None = None
    webhook_config: dict[str, Any] | None = None


class DeploymentStatusIn(BaseModel):
    action: Literal["pause", "resume"]


# ---------------------------------------------------------------------------
# Status and bindings
# ---------------------------------------------------------------------------

@router.get("/status")
async def voice_agents_status(current_actor: Actor = Depends(get_current_actor)) -> dict[str, Any]:
    """Whether live Samvaad is wired up. Never returns the key."""
    client = SamvaadClient()
    return {
        "mode": "fixture" if client.use_fixtures else "live",
        "workspace_configured": bool(client.org_id and client.workspace_id),
    }


@router.get("/agents", response_model=list[BindingOut])
async def list_my_agents(
    tenant_id: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Agents this business may use."""
    tid = await resolve_tenant(session, current_actor, tenant_id)
    rows = await session.execute(
        select(SamvaadAgentBinding).where(SamvaadAgentBinding.tenant_id == tid).order_by(SamvaadAgentBinding.created_at)
    )
    return [_binding_out(b) for b in rows.scalars().all()]


@router.get("/bindings", response_model=list[BindingOut])
async def list_bindings(
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    _require_admin(current_actor)
    rows = await session.execute(select(SamvaadAgentBinding).order_by(SamvaadAgentBinding.created_at))
    return [_binding_out(b) for b in rows.scalars().all()]


@router.put("/bindings", response_model=BindingOut)
async def upsert_binding(
    body: BindingIn,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Grant (or update) a business's use of one Samvaad agent. Admin only."""
    _require_admin(current_actor)
    tid = body.tenant_id.strip().lower()
    row = await session.execute(
        select(SamvaadAgentBinding).where(
            SamvaadAgentBinding.tenant_id == tid, SamvaadAgentBinding.app_id == body.app_id
        )
    )
    binding = row.scalar_one_or_none() or SamvaadAgentBinding(tenant_id=tid, app_id=body.app_id)
    binding.app_version = body.app_version
    binding.label = body.label
    binding.connection_id = body.connection_id
    binding.agent_phone_number = body.agent_phone_number
    session.add(binding)
    await session.commit()
    await session.refresh(binding)
    return _binding_out(binding)


@router.delete("/bindings/{binding_id}", status_code=204)
async def delete_binding(
    binding_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    _require_admin(current_actor)
    binding = await session.get(SamvaadAgentBinding, binding_id)
    if binding is None:
        raise HTTPException(status_code=404, detail="Binding not found")
    await session.delete(binding)
    await session.commit()


# ---------------------------------------------------------------------------
# Deployments (inbound numbers) and workspace analytics: admin only
# ---------------------------------------------------------------------------

@router.get("/deployments")
async def list_deployments(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_actor: Actor = Depends(get_current_actor),
):
    _require_admin(current_actor)
    return await SamvaadClient().list_deployments(offset=offset, limit=limit)


@router.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str, current_actor: Actor = Depends(get_current_actor)):
    _require_admin(current_actor)
    return await SamvaadClient().get_deployment(_validate_or_404(deployment_id))


@router.post("/deployments")
async def create_deployment(body: DeploymentIn, current_actor: Actor = Depends(get_current_actor)):
    """Connect an agent to a number for inbound calls. Goes live immediately."""
    _require_admin(current_actor)
    return await SamvaadClient().create_deployment(body.model_dump(exclude_none=True))


@router.put("/deployments/{deployment_id}/status")
async def set_deployment_status(
    deployment_id: str,
    body: DeploymentStatusIn,
    current_actor: Actor = Depends(get_current_actor),
):
    _require_admin(current_actor)
    return await SamvaadClient().update_deployment_status(_validate_or_404(deployment_id), body.action)


@router.get("/interactions")
async def list_interactions(
    app_id: str = Query(...),
    start_datetime: datetime | None = Query(None),
    end_datetime: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_transcript: bool = Query(False),
    current_actor: Actor = Depends(get_current_actor),
):
    """Every conversation an agent had in a range (default: last 7 days).

    Admin only: items carry callers' full phone numbers, and an agent may serve
    more than one business.
    """
    _require_admin(current_actor)
    end = end_datetime or datetime.now(UTC)
    start = start_datetime or end - timedelta(days=7)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if start >= end:
        raise HTTPException(status_code=422, detail="start_datetime must be before end_datetime")
    return await SamvaadClient().list_interactions(
        _validate_or_404(app_id),
        start_datetime=start.isoformat(),
        end_datetime=end.isoformat(),
        limit=limit,
        offset=offset,
        include_transcript=include_transcript,
    )


@router.get("/interactions/transcript", response_model=TranscriptOut)
async def admin_transcript(
    app_id: str = Query(...),
    interaction_id: str = Query(...),
    current_actor: Actor = Depends(get_current_actor),
):
    _require_admin(current_actor)
    data = await SamvaadClient().get_transcript(_validate_or_404(app_id), _validate_or_404(interaction_id))
    return TranscriptOut(interaction_id=interaction_id, messages=transcript_from_analytics(data))


def _validate_or_404(value: str) -> str:
    if not _ID.match(value or ""):
        raise HTTPException(status_code=404, detail="Not found")
    return value


# ---------------------------------------------------------------------------
# Outbound calls
# ---------------------------------------------------------------------------

def _webhook_url(request: Request, token: str) -> str:
    path = request.app.url_path_for("samvaad_outbound_webhook", token=token)
    base = (settings.public_base_url or "").strip().rstrip("/")
    if base:
        return f"{base}{path}"
    return str(request.url_for("samvaad_outbound_webhook", token=token))


@router.post("/calls", response_model=CallOut, status_code=202)
async def place_outbound_call(
    body: OutboundCallIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Have one of the business's agents call a number now.

    Returns at once with status "queued"; the outcome, duration and transcript
    arrive on the webhook and show up on GET /voice-agents/calls/{id}.
    """
    tid = await resolve_tenant(session, current_actor, body.tenant_id)
    binding = await _binding_for(session, tid, body.app_id)
    if not (binding.connection_id and binding.agent_phone_number and binding.app_version):
        raise HTTPException(status_code=409, detail="This agent has no outbound phone number")
    await _require_balance(session, tid)

    window_start = utcnow_naive() - timedelta(minutes=10)
    pending = await session.scalar(
        select(func.count()).select_from(SamvaadCallAttempt).where(
            SamvaadCallAttempt.tenant_id == tid,
            SamvaadCallAttempt.status == SamvaadCallStatus.QUEUED,
            SamvaadCallAttempt.created_at >= window_start,
        )
    )
    if (pending or 0) >= settings.samvaad_max_pending_calls:
        raise HTTPException(status_code=429, detail="Too many calls in progress; wait for some to finish")

    token = secrets.token_urlsafe(32)
    attempt = SamvaadCallAttempt(
        tenant_id=tid,
        actor_id=current_actor.id,
        app_id=binding.app_id,
        app_version=binding.app_version,
        user_phone_masked=_mask_phone(body.user_phone_number),
        webhook_token_hash=_hash_token(token),
    )
    session.add(attempt)
    await session.commit()

    overrides = {
        k: v
        for k, v in {
            "initial_language_name": body.initial_language_name,
            "initial_bot_message": body.initial_bot_message,
        }.items()
        if v
    }
    try:
        attempt_id = await SamvaadClient().create_outbound_call(
            app_id=binding.app_id,
            app_version=binding.app_version,
            connection_id=binding.connection_id,
            agent_phone_number=binding.agent_phone_number,
            user_phone_number=body.user_phone_number,
            webhook_url=_webhook_url(request, token),
            webhook_metadata={"call_id": str(attempt.id)},
            agent_variables=body.agent_variables,
            overrides=overrides or None,
        )
    except HTTPException as exc:
        attempt.status = SamvaadCallStatus.FAILED
        attempt.failure_reason = f"not placed: {exc.detail}"[:500]
        attempt.completed_at = utcnow_naive()
        await session.commit()
        raise
    attempt.attempt_id = attempt_id
    await session.commit()
    await session.refresh(attempt)
    logger.info("Samvaad outbound queued tenant=%s app=%s attempt=%s", tid, binding.app_id, attempt_id)
    return _call_out(attempt)


@router.get("/calls", response_model=list[CallOut])
async def list_calls(
    tenant_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    tid = await resolve_tenant(session, current_actor, tenant_id)
    rows = await session.execute(
        select(SamvaadCallAttempt)
        .where(SamvaadCallAttempt.tenant_id == tid)
        .order_by(SamvaadCallAttempt.created_at.desc())
        .limit(limit)
    )
    return [_call_out(c) for c in rows.scalars().all()]


async def _own_call(session: AsyncSession, actor: Actor, call_id: UUID) -> SamvaadCallAttempt:
    call = await session.get(SamvaadCallAttempt, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")
    # resolve_tenant raises 404 for a tenant the actor does not own.
    await resolve_tenant(session, actor, call.tenant_id)
    return call


@router.get("/calls/{call_id}", response_model=CallOut)
async def get_call(
    call_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    return _call_out(await _own_call(session, current_actor, call_id))


@router.get("/calls/{call_id}/transcript", response_model=TranscriptOut)
async def get_call_transcript(
    call_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """The transcript in the call's own language when Samvaad has it, else the webhook's English copy."""
    call = await _own_call(session, current_actor, call_id)
    if call.interaction_id:
        try:
            data = await SamvaadClient().get_transcript(call.app_id, call.interaction_id)
            messages = transcript_from_analytics(data)
            if messages:
                return TranscriptOut(interaction_id=call.interaction_id, messages=messages)
        except HTTPException as exc:
            logger.info("Transcript fetch failed for %s: %s", call.id, exc.detail)
    return TranscriptOut(interaction_id=call.interaction_id, messages=call.transcript or [])


class OutboundWebhookIn(BaseModel):
    attempt_id: str
    status: str
    app_id: str | None = None
    app_version: int | None = None
    duration: float | None = None
    interaction_id: str | None = None
    failure_reason: str | None = None
    final_agent_variables: dict[str, Any] | None = None
    interaction_transcript: list[dict[str, Any]] | None = None


@webhook_router.post("/outbound/{token}", name="samvaad_outbound_webhook")
async def outbound_webhook(
    token: str,
    payload: OutboundWebhookIn,
    session: AsyncSession = Depends(get_session),
):
    """Samvaad posts here once per outbound attempt. Idempotent; meters the wallet once."""
    if len(token) < 20 or len(token) > 100:
        raise HTTPException(status_code=404, detail="Not found")
    row = await session.execute(
        select(SamvaadCallAttempt).where(SamvaadCallAttempt.webhook_token_hash == _hash_token(token))
    )
    call = row.scalar_one_or_none()
    # The token is per call, so a mismatched attempt_id means a forged or misrouted post.
    if call is None or (call.attempt_id and not hmac.compare_digest(call.attempt_id, payload.attempt_id)):
        raise HTTPException(status_code=404, detail="Not found")
    if call.status in SamvaadCallStatus.TERMINAL and call.completed_at is not None:
        return {"ok": True, "duplicate": True}

    outcome = payload.status if payload.status in SamvaadCallStatus.TERMINAL else SamvaadCallStatus.FAILED
    call.attempt_id = call.attempt_id or payload.attempt_id
    call.status = outcome
    call.duration_seconds = payload.duration
    call.interaction_id = (payload.interaction_id or "")[:120] or None
    call.failure_reason = (payload.failure_reason or "")[:500] or None
    call.final_agent_variables = payload.final_agent_variables
    call.transcript = transcript_from_webhook(payload.interaction_transcript) or None
    call.completed_at = utcnow_naive()
    await session.commit()

    billed = None
    if outcome == SamvaadCallStatus.CONNECTED and (payload.duration or 0) > 0:
        res = await BillingService(session).meter_call(
            call.tenant_id, int(math.ceil(payload.duration or 0)), f"samvaad:{call.attempt_id}"
        )
        await session.commit()
        billed = res.get("last_call_debit_inr")
    return {"ok": True, "billed_inr": billed}


# ---------------------------------------------------------------------------
# Live voice session proxy
# ---------------------------------------------------------------------------

@router.websocket("/ws/{app_id}")
async def voice_session_proxy(
    ws: WebSocket,
    app_id: str,
    token: str = Query(""),
    tenant_id: str | None = Query(None),
    language: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Talk to an agent from the app. The Samvaad session runs here, never on the phone."""
    try:
        actor = await link_actor(session, verify_access_token(token))
    except InvalidAccessToken:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        if not _ID.match(app_id):
            raise HTTPException(status_code=404, detail="Agent not found")
        if language and language not in LANGUAGE_NAMES:
            raise HTTPException(status_code=422, detail="Unknown language")
        tid = await resolve_tenant(session, actor, tenant_id)
        binding = await _binding_for(session, tid, app_id)
        await _require_balance(session, tid)
    except HTTPException as exc:
        await ws.accept()
        await ws.send_text(json.dumps({"type": "error", "status": exc.status_code, "detail": exc.detail}))
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws.accept()
    send_lock = asyncio.Lock()
    last_rate: dict[str, int] = {}

    async def send_json(msg: dict[str, Any]) -> None:
        async with send_lock:
            await ws.send_text(json.dumps(msg))

    async def on_transcript(role: str, content: str) -> None:
        await send_json({"type": "transcript", "role": role, "content": content})

    async def on_audio(pcm: bytes, sample_rate: int) -> None:
        async with send_lock:
            if last_rate.get("rate") != sample_rate:
                last_rate["rate"] = sample_rate
                await ws.send_text(json.dumps({"type": "audio_format", "encoding": "pcm_s16le", "sample_rate": sample_rate}))
            await ws.send_bytes(pcm)

    async def on_event(kind: str, extra: dict[str, Any]) -> None:
        await send_json({"type": "event", "event": kind, **extra})

    try:
        agent = open_voice_session(
            app_id=binding.app_id,
            app_version=binding.app_version,
            user_identifier=f"{tid}:{actor.id}",
            on_transcript=on_transcript,
            on_audio=on_audio,
            on_event=on_event,
            initial_language_name=language,
        )
    except HTTPException as exc:
        await send_json({"type": "error", "status": exc.status_code, "detail": exc.detail})
        await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    started = time.monotonic()
    reason = "client_closed"
    try:
        await agent.start()
        if not await agent.wait_for_connect(timeout=10.0):
            reason = "agent_unavailable"
            await send_json({"type": "error", "status": 502, "detail": "Voice agent did not connect"})
            return
        await send_json({"type": "ready", "interaction_id": agent.get_interaction_id()})

        async def pump_client() -> str:
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.disconnect":
                    return "client_closed"
                data = msg.get("bytes")
                if data:
                    if len(data) > _MAX_FRAME_BYTES:
                        return "frame_too_large"
                    await agent.send_audio(data)
                    continue
                text = msg.get("text")
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except ValueError:
                    continue
                if obj.get("type") == "end":
                    return "client_ended"
                if obj.get("type") == "text" and isinstance(obj.get("text"), str) and obj["text"].strip():
                    await agent.send_text(obj["text"][:2000])

        client_task = asyncio.create_task(pump_client())
        agent_task = asyncio.create_task(agent.wait_for_disconnect())
        done, pending = await asyncio.wait(
            {client_task, agent_task},
            timeout=settings.samvaad_max_session_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        if client_task in done and not client_task.cancelled() and client_task.exception() is None:
            reason = client_task.result()
        elif agent_task in done:
            reason = "agent_ended"
        elif not done:
            reason = "time_limit"
        else:
            reason = "error"
    except WebSocketDisconnect:
        reason = "client_closed"
    except Exception as exc:  # the SDK raises bare Exception on connect failures
        reason = "error"
        logger.warning("Samvaad session error app=%s: %s", app_id, type(exc).__name__)
    finally:
        interaction_id = agent.get_interaction_id()
        try:
            await agent.stop()
        except Exception:
            pass
        seconds = int(math.ceil(time.monotonic() - started))
        if interaction_id and seconds > 0:
            try:
                await BillingService(session).meter_call(tid, seconds, f"samvaad-live:{interaction_id}")
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Could not meter live session %s", interaction_id)
        try:
            await send_json({"type": "ended", "reason": reason, "seconds": seconds})
            await ws.close()
        except Exception:
            pass
