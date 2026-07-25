from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActorType(str, Enum):
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class Role(str, Enum):
    INITIATOR = "initiator"
    APPROVER = "approver"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    OBSERVER = "observer"
    ADMIN = "admin"
    MANAGER = "manager"


class Permission(str, Enum):
    CREATE_WORKFLOW = "create:workflow"
    READ_WORKFLOW = "read:workflow"
    UPDATE_WORKFLOW = "update:workflow"
    CANCEL_WORKFLOW = "cancel:workflow"
    APPROVE = "approve"
    REJECT = "reject"
    EXECUTE = "execute"
    VERIFY = "verify"
    MANAGE_ACTORS = "manage:actors"
    VIEW_ANALYTICS = "view:analytics"
    CONFIGURE_INTEGRATIONS = "configure:integrations"


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[ActorType] = mapped_column(SAEnum(ActorType), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    roles: Mapped[List[Role]] = mapped_column(JSON, nullable=False, default=list)
    permissions: Mapped[List[Permission]] = mapped_column(JSON, nullable=False, default=list)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    extra_attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column("extra_attributes", JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def capabilities(self) -> List[str]:
        if not self.extra_attributes:
            return []
        return self.extra_attributes.get("capabilities", [])

    @property
    def trust_score(self) -> float:
        if not self.extra_attributes:
            return 1.0
        return self.extra_attributes.get("trust_score", 1.0)
