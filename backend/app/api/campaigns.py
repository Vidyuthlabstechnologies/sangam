"""Bulk AI calling campaigns: upload a list, set a goal, let the agent call everyone.

Flow:
  POST /campaigns                      create (draft): goal, target, language, agent
  POST /campaigns/{id}/contacts        upload a CSV (phone, name, language, extra columns)
  POST /campaigns/{id}/start           begin dialling, up to `concurrency` calls at once
  GET  /campaigns/{id}/live            progress to target, calls in progress, latest outcomes
  GET  /campaigns/{id}/contacts        every contact with its outcome and summary
  GET  /campaigns/{id}/contacts/{cid}  one call, with transcript
  POST /campaigns/{id}/pause | resume | cancel
  POST /campaigns/demo                 a ready-made simulation with sample contacts

Live campaigns dial through the business's bound Samvaad agent and spend call
credit; simulations dial nobody and cost nothing. See app/core/campaign_engine.py
for the dialling loop and the Indian calling rules it enforces.
"""
from __future__ import annotations

import random
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.api.onboarding import resolve_tenant
from app.api.voice_agents import (
    _binding_for,
    _require_balance,
    _validate_id,
    _webhook_url,
)
from app.core import campaign_engine as engine
from app.core.billing_service import BillingService
from app.core.samvaad import LANGUAGE_NAMES
from app.db.session import get_session
from app.models.actor import Actor
from app.models.campaign import (
    CallCampaign,
    CampaignContact,
    CampaignStatus,
    ContactStatus,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _webhook_url_for(request: Request):
    return lambda token: _webhook_url(request, token)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CampaignIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    mode: Literal["live", "simulation"] = "live"
    app_id: str | None = None
    goal: str = Field(..., min_length=1, max_length=200)
    target_count: int = Field(..., ge=1, le=100_000)
    language: str = "English"
    pitch: str | None = Field(None, max_length=1000)
    opening_line: str | None = Field(None, max_length=500)
    business_name: str | None = Field(None, max_length=120)
    concurrency: int = Field(20, ge=1, le=1000)
    max_attempts: int = Field(1, ge=1, le=3)
    window_start_hour: int = Field(engine.LEGAL_START_HOUR, ge=0, le=23)
    window_end_hour: int = Field(engine.LEGAL_END_HOUR, ge=1, le=24)
    success_variable: str = Field("goal_achieved", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    success_values: list[str] = Field(default_factory=lambda: ["true", "yes"], max_length=10)
    consent_confirmed: bool = False
    sim_speed: float = Field(1.0, ge=1.0, le=20.0)
    tenant_id: str | None = None

    @field_validator("app_id")
    @classmethod
    def _app(cls, v: str | None) -> str | None:
        return _validate_id(v, "app_id") if v else None

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        v = engine.normalize_language(v) or v
        if v not in LANGUAGE_NAMES:
            raise ValueError(f"language must be one of {sorted(LANGUAGE_NAMES)}")
        return v

    @model_validator(mode="after")
    def _check(self) -> CampaignIn:
        if self.window_start_hour < engine.LEGAL_START_HOUR or self.window_end_hour > engine.LEGAL_END_HOUR:
            raise ValueError("Calling hours must fall between 9:00 and 21:00 IST (TRAI)")
        if self.window_start_hour >= self.window_end_hour:
            raise ValueError("window_start_hour must be before window_end_hour")
        if self.mode == "live" and not self.app_id:
            raise ValueError("A live campaign needs app_id: the voice agent that makes the calls")
        return self


class ContactsIn(BaseModel):
    csv: str = Field(..., min_length=1, max_length=2_000_000)


class CampaignOut(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    mode: str
    app_id: str | None
    goal: str
    target_count: int
    language: str
    pitch: str | None
    business_name: str
    concurrency: int
    max_attempts: int
    window_start_hour: int
    window_end_hour: int
    consent_confirmed: bool
    status: str
    hold_reason: str | None
    sim_speed: float
    success_count: int
    contacts_total: int
    counts: dict[str, int]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class ContactOut(BaseModel):
    id: UUID
    name: str
    phone: str
    language: str | None
    status: str
    attempts: int
    succeeded: bool
    opted_out: bool
    summary: str | None
    duration_seconds: float | None
    dialed_at: datetime | None
    completed_at: datetime | None


class ContactDetailOut(ContactOut):
    transcript: list[dict[str, Any]]


class ActiveCallOut(BaseModel):
    id: UUID
    name: str
    phone: str
    language: str | None
    phase: str
    elapsed_seconds: int
    line: dict[str, Any] | None


class LiveOut(BaseModel):
    campaign: CampaignOut
    progress: float
    active: list[ActiveCallOut]
    recent: list[ContactOut]
    versus_telecaller: dict[str, Any]
    simulated: bool


def _campaign_out(c: CallCampaign, by_status: dict[str, int]) -> CampaignOut:
    return CampaignOut(
        id=c.id, tenant_id=c.tenant_id, name=c.name, mode=c.mode, app_id=c.app_id, goal=c.goal,
        target_count=c.target_count, language=c.language, pitch=c.pitch, business_name=c.business_name,
        concurrency=c.concurrency, max_attempts=c.max_attempts, window_start_hour=c.window_start_hour,
        window_end_hour=c.window_end_hour, consent_confirmed=c.consent_confirmed, status=c.status,
        hold_reason=c.hold_reason, sim_speed=c.sim_speed, success_count=c.success_count,
        contacts_total=sum(by_status.values()), counts=by_status, started_at=c.started_at,
        finished_at=c.finished_at, created_at=c.created_at,
    )


def _contact_out(c: CampaignContact) -> ContactOut:
    return ContactOut(
        id=c.id, name=c.name, phone=engine.mask_phone(c.phone), language=c.language, status=c.status,
        attempts=c.attempts, succeeded=c.succeeded, opted_out=c.opted_out, summary=c.summary,
        duration_seconds=c.duration_seconds, dialed_at=c.dialed_at, completed_at=c.completed_at,
    )


async def _own_campaign(session: AsyncSession, actor: Actor, campaign_id: UUID) -> CallCampaign:
    campaign = await session.get(CallCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await resolve_tenant(session, actor, campaign.tenant_id)  # 404 for someone else's
    return campaign


async def _advance(session: AsyncSession, campaign_id: UUID, webhook_url_for: Any) -> CallCampaign:
    campaign = await engine.advance(session, campaign_id, webhook_url_for)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


async def _out(session: AsyncSession, campaign: CallCampaign) -> CampaignOut:
    return _campaign_out(campaign, await engine.counts(session, campaign.id))


# ---------------------------------------------------------------------------
# Create and upload
# ---------------------------------------------------------------------------

async def _default_business_name(session: AsyncSession, tenant_id: str) -> str:
    wallet = await BillingService(session).get_wallet(tenant_id)
    return (getattr(wallet, "business_name", None) or "").strip()


@router.post("", response_model=CampaignOut, status_code=201)
async def create_campaign(
    body: CampaignIn,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    tid = await resolve_tenant(session, current_actor, body.tenant_id)
    if body.mode == "live":
        binding = await _binding_for(session, tid, body.app_id or "")
        if not (binding.connection_id and binding.agent_phone_number and binding.app_version):
            raise HTTPException(status_code=409, detail="This agent has no outbound phone number")
    campaign = CallCampaign(
        tenant_id=tid,
        created_by=current_actor.id,
        name=body.name.strip(),
        mode=body.mode,
        app_id=body.app_id,
        goal=body.goal.strip(),
        target_count=body.target_count,
        language=body.language,
        pitch=(body.pitch or "").strip() or None,
        opening_line=(body.opening_line or "").strip() or None,
        business_name=(body.business_name or "").strip() or await _default_business_name(session, tid),
        concurrency=body.concurrency,
        max_attempts=body.max_attempts,
        window_start_hour=body.window_start_hour,
        window_end_hour=body.window_end_hour,
        success_variable=body.success_variable,
        success_values=[v.strip().lower() for v in body.success_values if v.strip()],
        consent_confirmed=body.consent_confirmed,
        sim_speed=body.sim_speed if body.mode == "simulation" else 1.0,
    )
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    return await _out(session, campaign)


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    tenant_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    tid = await resolve_tenant(session, current_actor, tenant_id)
    rows = await session.execute(
        select(CallCampaign).where(CallCampaign.tenant_id == tid).order_by(CallCampaign.created_at.desc()).limit(limit)
    )
    return [await _out(session, c) for c in rows.scalars().all()]


async def _add_contacts(session: AsyncSession, campaign: CallCampaign, parsed: list[dict[str, Any]]) -> dict[str, int]:
    existing = set(
        (await session.execute(select(CampaignContact.phone).where(CampaignContact.campaign_id == campaign.id))).scalars().all()
    )
    total = len(existing)
    blocked = await engine._blocked_numbers(session, campaign.tenant_id, [p["phone"] for p in parsed])
    position = await session.scalar(
        select(func.coalesce(func.max(CampaignContact.position), 0)).where(CampaignContact.campaign_id == campaign.id)
    ) or 0
    added = duplicates = suppressed = 0
    for row in parsed:
        if row["phone"] in existing:
            duplicates += 1
            continue
        if total >= engine.MAX_CONTACTS:
            raise HTTPException(status_code=413, detail=f"A campaign holds at most {engine.MAX_CONTACTS} contacts")
        existing.add(row["phone"])
        total += 1
        position += 1
        contact = CampaignContact(
            campaign_id=campaign.id, position=position, name=row["name"], phone=row["phone"],
            language=row["language"], variables=row["variables"],
        )
        if row["dnd"] or row["phone"] in blocked:
            contact.status = ContactStatus.SUPPRESSED
            contact.summary = "Not called: registered on DND." if row["dnd"] else "Not called: on the do-not-call list."
            suppressed += 1
        else:
            added += 1
        session.add(contact)
    return {"added": added, "duplicates": duplicates, "suppressed": suppressed}


@router.post("/{campaign_id}/contacts")
async def upload_contacts(
    campaign_id: UUID,
    body: ContactsIn,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Add contacts from CSV text. Duplicates and do-not-call numbers are dropped."""
    campaign = await _own_campaign(session, current_actor, campaign_id)
    if campaign.status in CampaignStatus.FINISHED:
        raise HTTPException(status_code=409, detail="This campaign has ended")
    parsed, invalid = engine.parse_contacts_csv(body.csv)
    result = await _add_contacts(session, campaign, parsed)
    await session.commit()
    return {**result, "invalid": invalid[:50], "invalid_count": len(invalid), "campaign": await _out(session, campaign)}


# ---------------------------------------------------------------------------
# Control
# ---------------------------------------------------------------------------

@router.post("/{campaign_id}/start", response_model=CampaignOut)
async def start_campaign(
    campaign_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    campaign = await _own_campaign(session, current_actor, campaign_id)
    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.PAUSED):
        raise HTTPException(status_code=409, detail=f"Campaign is {campaign.status}")
    by_status = await engine.counts(session, campaign.id)
    if by_status.get(ContactStatus.PENDING, 0) == 0:
        raise HTTPException(status_code=409, detail="Upload contacts first")
    if campaign.mode == "live":
        if not campaign.consent_confirmed:
            raise HTTPException(
                status_code=409,
                detail="Confirm the list is scrubbed against DND (NCPR) or has opted in before calling",
            )
        await _binding_for(session, campaign.tenant_id, campaign.app_id or "")
        await _require_balance(session, campaign.tenant_id)
    campaign.status = CampaignStatus.RUNNING
    campaign.started_at = campaign.started_at or engine.now()
    await session.commit()
    campaign = await _advance(session, campaign.id, _webhook_url_for(request))
    return await _out(session, campaign)


@router.post("/{campaign_id}/resume", response_model=CampaignOut)
async def resume_campaign(
    campaign_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    return await start_campaign(campaign_id, request, session, current_actor)


@router.post("/{campaign_id}/pause", response_model=CampaignOut)
async def pause_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Stop placing new calls. Calls already live finish normally."""
    campaign = await _own_campaign(session, current_actor, campaign_id)
    if campaign.status != CampaignStatus.RUNNING:
        raise HTTPException(status_code=409, detail=f"Campaign is {campaign.status}")
    campaign.status = CampaignStatus.PAUSED
    campaign.hold_reason = None
    await session.commit()
    return await _out(session, campaign)


@router.post("/{campaign_id}/cancel", response_model=CampaignOut)
async def cancel_campaign(
    campaign_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    campaign = await _own_campaign(session, current_actor, campaign_id)
    if campaign.status in CampaignStatus.FINISHED:
        raise HTTPException(status_code=409, detail=f"Campaign is {campaign.status}")
    campaign.status = CampaignStatus.CANCELLED
    campaign.finished_at = engine.now()
    campaign.hold_reason = None
    rows = await session.execute(
        select(CampaignContact).where(
            CampaignContact.campaign_id == campaign.id, CampaignContact.status == ContactStatus.PENDING
        )
    )
    for contact in rows.scalars().all():
        contact.status = ContactStatus.SKIPPED
        contact.summary = "Not called: the campaign was cancelled."
    await session.commit()
    return await _out(session, campaign)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    campaign = await _own_campaign(session, current_actor, campaign_id)
    if campaign.status == CampaignStatus.RUNNING:
        campaign = await _advance(session, campaign.id, _webhook_url_for(request))
    return await _out(session, campaign)


@router.get("/{campaign_id}/live", response_model=LiveOut)
async def campaign_live(
    campaign_id: UUID,
    request: Request,
    active_limit: int = Query(60, ge=0, le=300),
    recent_limit: int = Query(30, ge=0, le=200),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Everything the live board shows. Polling this also keeps the campaign dialling."""
    campaign = await _own_campaign(session, current_actor, campaign_id)
    if campaign.status in (CampaignStatus.RUNNING, CampaignStatus.TARGET_REACHED, CampaignStatus.COMPLETED):
        # Settle calls still live after the goal was met, too.
        campaign = await _advance(session, campaign.id, _webhook_url_for(request))
    now = engine.now()
    by_status = await engine.counts(session, campaign.id)

    active_rows = await session.execute(
        select(CampaignContact)
        .where(CampaignContact.campaign_id == campaign.id, CampaignContact.status == ContactStatus.DIALING)
        .order_by(CampaignContact.dialed_at)
        .limit(active_limit)
    )
    active = []
    for c in active_rows.scalars().all():
        p = engine.live_progress(campaign, c, now)
        active.append(ActiveCallOut(
            id=c.id, name=c.name, phone=engine.mask_phone(c.phone), language=c.language or campaign.language,
            phase=p["phase"], elapsed_seconds=p["elapsed_seconds"], line=p.get("line"),
        ))

    recent_rows = await session.execute(
        select(CampaignContact)
        .where(CampaignContact.campaign_id == campaign.id, CampaignContact.completed_at.is_not(None))
        .order_by(CampaignContact.completed_at.desc())
        .limit(recent_limit)
    )
    done_rows = await session.execute(
        select(CampaignContact.status, CampaignContact.duration_seconds).where(
            CampaignContact.campaign_id == campaign.id, CampaignContact.completed_at.is_not(None)
        )
    )
    return LiveOut(
        campaign=_campaign_out(campaign, by_status),
        progress=min(campaign.success_count / campaign.target_count, 1.0),
        active=active,
        recent=[_contact_out(c) for c in recent_rows.scalars().all()],
        versus_telecaller=engine.versus_telecaller(
            [(s, d) for s, d in done_rows.all()], campaign.started_at, campaign.finished_at, now,
            speed=campaign.sim_speed if campaign.mode == "simulation" else 1.0,
        ),
        simulated=campaign.mode == "simulation",
    )


@router.get("/{campaign_id}/contacts", response_model=list[ContactOut])
async def list_contacts(
    campaign_id: UUID,
    status: str | None = Query(None),
    succeeded: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    campaign = await _own_campaign(session, current_actor, campaign_id)
    stmt = select(CampaignContact).where(CampaignContact.campaign_id == campaign.id)
    if status:
        stmt = stmt.where(CampaignContact.status == status)
    if succeeded is not None:
        stmt = stmt.where(CampaignContact.succeeded == succeeded)
    rows = await session.execute(stmt.order_by(CampaignContact.position).offset(offset).limit(limit))
    return [_contact_out(c) for c in rows.scalars().all()]


@router.get("/{campaign_id}/contacts/{contact_id}", response_model=ContactDetailOut)
async def get_contact(
    campaign_id: UUID,
    contact_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    campaign = await _own_campaign(session, current_actor, campaign_id)
    contact = await session.get(CampaignContact, contact_id)
    if contact is None or contact.campaign_id != campaign.id:
        raise HTTPException(status_code=404, detail="Contact not found")
    transcript = contact.transcript or []
    if not transcript and contact.status == ContactStatus.DIALING and contact.sim_plan:
        # Show the simulated call so far.
        now = engine.now()
        turns = engine.simulated_transcript(campaign, contact, contact.sim_plan)
        line = engine.live_progress(campaign, contact, now).get("line")
        transcript = turns[: turns.index(line) + 1] if line in turns else []
    return ContactDetailOut(**_contact_out(contact).model_dump(), transcript=transcript)


# ---------------------------------------------------------------------------
# One-tap demo
# ---------------------------------------------------------------------------

_SAMPLE_NAMES = {
    "Telugu": ["Srinivas Reddy", "Lakshmi Prasanna", "Venkatesh Rao", "Padmavathi", "Ravi Teja", "Swathi Naidu",
               "Mahesh Babu K", "Anitha Chowdary", "Suresh Varma", "Kavya Sri", "Naveen Kumar", "Sravani"],
    "Hindi": ["Rahul Sharma", "Priyanka Verma", "Amit Gupta", "Sunita Yadav", "Vikram Singh", "Neha Agarwal",
              "Rajesh Kumar", "Pooja Mishra", "Sandeep Jain", "Kavita Joshi", "Manoj Tiwari", "Anjali Saxena"],
    "English": ["Arjun Menon", "Meera Iyer", "Karthik Raman", "Divya Pillai", "Rohan D'Souza", "Sneha Kulkarni",
                "Aditya Rao", "Nisha Fernandes", "Varun Nair", "Ishita Bose", "Siddharth Shetty", "Tara Mathew"],
}


class DemoIn(BaseModel):
    contacts: int = Field(300, ge=10, le=1000)
    target_count: int = Field(50, ge=1, le=1000)
    concurrency: int = Field(100, ge=1, le=300)
    goal: str = Field("Site visit booked", min_length=1, max_length=200)
    pitch: str = Field("Outer Ring Road villa plots", max_length=1000)
    business_name: str = Field("Sri Sai Developers", max_length=120)
    sim_speed: float = Field(1.0, ge=1.0, le=20.0)
    start: bool = True
    tenant_id: str | None = None


@router.post("/demo", response_model=CampaignOut, status_code=201)
async def create_demo(
    body: DemoIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """A simulated campaign with sample Telugu, Hindi and English contacts. Dials nobody."""
    tid = await resolve_tenant(session, current_actor, body.tenant_id)
    campaign = CallCampaign(
        tenant_id=tid, created_by=current_actor.id, name=f"{body.goal} (simulation)", mode="simulation",
        goal=body.goal, target_count=body.target_count, language="Telugu", pitch=body.pitch,
        business_name=body.business_name, concurrency=body.concurrency, success_values=["true"],
        sim_speed=body.sim_speed,
    )
    session.add(campaign)
    await session.flush()
    rng = random.Random(str(campaign.id))
    languages = ["Telugu"] * 5 + ["Hindi"] * 3 + ["English"] * 2
    rows = []
    for i in range(body.contacts):
        lang = languages[i % len(languages)]
        rows.append({
            "name": rng.choice(_SAMPLE_NAMES[lang]),
            # Sample numbers: a simulation never dials them.
            "phone": f"+9190000{i:05d}",
            "language": lang,
            "variables": None,
            "dnd": False,
        })
    await _add_contacts(session, campaign, rows)
    await session.commit()
    if body.start:
        campaign.status = CampaignStatus.RUNNING
        campaign.started_at = engine.now()
        await session.commit()
        campaign = await _advance(session, campaign.id, _webhook_url_for(request))
    return await _out(session, campaign)
