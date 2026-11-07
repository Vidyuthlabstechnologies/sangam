"""A callback or visit request captured by the voice agent."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CallbackStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CLOSED = "closed"


class VoiceCallback(Base):
    __tablename__ = "voice_callbacks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The platform's call id. UNIQUE so a webhook retry is idempotent.
    call_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    caller_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    caller_phone: Mapped[str] = mapped_column(String(16), nullable=False)
    service: Mapped[str] = mapped_column(String(32), nullable=False, default="unclear")
    preferred_time: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    urgency: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[CallbackStatus] = mapped_column(
        SAEnum(CallbackStatus), nullable=False, default=CallbackStatus.NEW
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
