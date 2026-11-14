"""Bulk calling campaigns: one goal, a contact list, many AI calls in parallel.

A campaign belongs to one business (tenant). It dials its contacts through a
Samvaad agent bound to that tenant, keeps up to ``concurrency`` calls live at
once, and stops dialling the moment ``target_count`` contacts said yes.

A campaign in ``simulation`` mode places no real calls and spends nothing: the
engine plays each call out on the server clock with a scripted conversation, so
the whole flow (dialling, live progress, outcomes, transcripts) can be shown or
tested without telephony. Simulated results are always labelled as such.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.sangamitra_release import utcnow_naive


class CampaignStatus:
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    # Stopped dialling because the goal was met; calls already live still finish.
    TARGET_REACHED = "target_reached"
    # Every contact was tried.
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FINISHED = frozenset({TARGET_REACHED, COMPLETED, CANCELLED})


class ContactStatus:
    PENDING = "pending"
    DIALING = "dialing"  # placed, outcome not in yet
    CONNECTED = "connected"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    # Never dialled, by rule: on the business's do-not-call list, or the campaign
    # ended first.
    SUPPRESSED = "suppressed"
    SKIPPED = "skipped"
    FINAL = frozenset({CONNECTED, NO_ANSWER, BUSY, FAILED, SUPPRESSED, SKIPPED})
    RETRYABLE = frozenset({NO_ANSWER, BUSY})


class CallCampaign(Base):
    __tablename__ = "call_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # "live" dials through Samvaad; "simulation" plays calls out on the server.
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    # Null only in simulation mode.
    app_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # What one success is, in the owner's words: "site visit booked".
    goal: Mapped[str] = mapped_column(String(200), nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # The agent sets this variable at the end of a call; a value in
    # success_values (case-insensitive) counts as one success.
    success_variable: Mapped[str] = mapped_column(String(64), nullable=False, default="goal_achieved")
    success_values: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Samvaad language name the agent opens in; a contact's own language wins.
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="English")
    # Opening line; {name} is filled per contact.
    opening_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the agent pitches; passed to the agent as the "pitch" variable.
    pitch: Mapped[str | None] = mapped_column(Text, nullable=True)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Calling window in India Standard Time, as whole hours [start, end).
    window_start_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    window_end_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=21)
    # The owner confirmed every number is scrubbed against NCPR (DND) or opted in.
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Shown as "calling from ..." in the agent's introduction.
    business_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CampaignStatus.DRAFT)
    # Why a running campaign is not dialling right now (no credit, outside hours).
    hold_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Simulation only: how many times faster than real time calls play out.
    sim_speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)


class CampaignContact(Base):
    __tablename__ = "campaign_contacts"
    __table_args__ = (UniqueConstraint("campaign_id", "phone", name="uq_campaign_contact_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_campaigns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Upload order; dialling goes in this order.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Full E.164: needed to dial. Never returned by the API; responses mask it.
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Extra CSV columns, passed to the agent as variables.
    variables: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False, default=ContactStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    transcript: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # Simulation only: when the call ends and how it goes. Never set on live calls.
    sim_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dialed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DoNotCallEntry(Base):
    """A number this business must never call again (asked to stop, or a DND list)."""

    __tablename__ = "do_not_call_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_dnc_tenant_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False, default="opted_out")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
