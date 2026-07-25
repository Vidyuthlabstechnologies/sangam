from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class SLAConfig(Base):
    __tablename__ = "sla_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    escalation_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    escalation_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    escalation_actor = relationship("Actor", foreign_keys=[escalation_actor_id])


class SLATracking(Base):
    __tablename__ = "sla_tracking"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    sla_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sla_configs.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    warning_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalation_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    breached_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    workflow = relationship("Workflow")
    sla_config = relationship("SLAConfig")
