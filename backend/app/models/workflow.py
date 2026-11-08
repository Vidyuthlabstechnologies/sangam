from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, Enum as SAEnum, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class WorkflowPhase(str, Enum):
    INITIATION = "initiation"
    APPROVAL = "approval"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    SETTLEMENT = "settlement"
    EXCEPTION = "exception"


class WorkflowState(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    initiator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=False)
    # Zitadel organization that owns this workflow. Taken from the caller's token, never from the body.
    organization_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    current_phase: Mapped[WorkflowPhase] = mapped_column(SAEnum(WorkflowPhase), nullable=False, default=WorkflowPhase.INITIATION)
    state: Mapped[WorkflowState] = mapped_column(SAEnum(WorkflowState), nullable=False, default=WorkflowState.DRAFT)
    phases: Mapped[List[WorkflowPhase]] = mapped_column(JSON, nullable=False, default=list)
    extra_attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column("extra_attributes", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    initiator = relationship("Actor", foreign_keys=[initiator_id])
    approvals = relationship("Approval", back_populates="workflow", lazy="selectin")
    handoffs = relationship("Handoff", back_populates="workflow", lazy="selectin")
    waiting_events = relationship("WaitingEvent", back_populates="workflow", lazy="selectin")
    exceptions = relationship("ExceptionWorkflow", back_populates="parent_workflow", lazy="selectin")

    @property
    def semantic_boundaries(self) -> List[Dict]:
        return self.extra_attributes.get("semantic_boundaries", []) if self.extra_attributes else []


class WaitingEvent(Base):
    __tablename__ = "waiting_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    sla_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="waiting_events")
    actor = relationship("Actor")
