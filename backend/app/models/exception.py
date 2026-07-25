from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Enum as SAEnum, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class ExceptionTrigger(str, Enum):
    ERROR = "error"
    TIMEOUT = "timeout"
    DEVIATION = "deviation"
    CHANGE_REQUEST = "change_request"
    DISPUTE = "dispute"
    DELAY = "delay"
    ESCALATION = "escalation"


class ExceptionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionWorkflow(Base):
    __tablename__ = "exception_workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    trigger: Mapped[ExceptionTrigger] = mapped_column(SAEnum(ExceptionTrigger), nullable=False)
    severity: Mapped[ExceptionSeverity] = mapped_column(SAEnum(ExceptionSeverity), nullable=False, default=ExceptionSeverity.MEDIUM)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    phases: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    learning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    parent_workflow = relationship("Workflow", back_populates="exceptions")
    assignee = relationship("Actor", foreign_keys=[assigned_to])
