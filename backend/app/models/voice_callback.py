"""A callback or visit request captured by the voice agent."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CallbackStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CLOSED = "closed"


class VoiceCallback(Base):
    __tablename__ = "voice_callbacks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The platform's call id. UNIQUE so a webhook retry is idempotent.
    call_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True, default="abhishek-industries")
    caller_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    caller_phone: Mapped[str] = mapped_column(String(16), nullable=False)
    service: Mapped[str] = mapped_column(String(64), nullable=False, default="unclear")
    preferred_time: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    urgency: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    recording_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[CallbackStatus] = mapped_column(
        SAEnum(CallbackStatus), nullable=False, default=CallbackStatus.NEW
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
