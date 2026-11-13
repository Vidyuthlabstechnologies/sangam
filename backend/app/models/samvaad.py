"""Sarvam Voice Agents (Samvaad): which business may use which agent, and the calls placed.

All agents live in ONE Samvaad workspace (the platform's key). A binding is the
admin's grant that lets one tenant drive one agent through one phone number;
without it, a signed-in user cannot spend platform minutes on any agent.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.sangamitra_release import utcnow_naive


class SamvaadAgentBinding(Base):
    __tablename__ = "samvaad_agent_bindings"
    __table_args__ = (UniqueConstraint("tenant_id", "app_id", name="uq_samvaad_binding_tenant_app"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    app_id: Mapped[str] = mapped_column(String(200), nullable=False)
    # None = the latest committed version, for web sessions. Outbound calls need a number.
    app_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # Telephony leg for outbound calls; both empty = web sessions only.
    connection_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agent_phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)


class SamvaadCallStatus:
    QUEUED = "queued"
    CONNECTED = "connected"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    TERMINAL = frozenset({CONNECTED, NO_ANSWER, BUSY, FAILED})


class SamvaadCallAttempt(Base):
    __tablename__ = "samvaad_call_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Samvaad's id. Null only between our insert and its response.
    attempt_id: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    app_id: Mapped[str] = mapped_column(String(200), nullable=False)
    app_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # Masked: the full number is needed only to place the call.
    user_phone_masked: Mapped[str] = mapped_column(String(24), nullable=False)
    # sha256 of the secret in the webhook URL. The payload is unsigned, so the URL is the proof.
    webhook_token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SamvaadCallStatus.QUEUED)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    interaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_agent_variables: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    transcript: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
