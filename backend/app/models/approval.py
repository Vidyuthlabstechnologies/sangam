from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, Enum as SAEnum, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class ApprovalStrategy(str, Enum):
    ANY = "any"
    ALL = "all"
    THRESHOLD = "threshold"


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    strategy: Mapped[ApprovalStrategy] = mapped_column(SAEnum(ApprovalStrategy), nullable=False, default=ApprovalStrategy.ALL)
    required_count: Mapped[Optional[int]] = mapped_column(default=None, nullable=True)
    required_actors: Mapped[List[uuid.UUID]] = mapped_column(JSON, nullable=False, default=list)
    approved_by: Mapped[List[uuid.UUID]] = mapped_column(JSON, nullable=False, default=list)
    rejected_by: Mapped[List[uuid.UUID]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[ApprovalStatus] = mapped_column(SAEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING)
    condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalated_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="approvals")
