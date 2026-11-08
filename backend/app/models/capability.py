"""Capabilities registered by an actor. The database is the authorization boundary.

Qdrant is an optional search index. Rows here are what list/search/delete are
allowed to return, even when the index is empty or missing a tenant payload.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegisteredCapability(Base):
    __tablename__ = "registered_capabilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    tags: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    language: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    avg_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_cost_per_call: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
