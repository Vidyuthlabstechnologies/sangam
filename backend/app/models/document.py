from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Text, JSON, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class ExtractionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ExtractedDocument(Base):
    """A document submitted for automated extraction.

    Retains both the raw extracted markdown and the structured result. The
    raw text is kept deliberately: in a regulated context, a reviewer must
    be able to see what the model actually read before trusting the fields
    derived from it.
    """

    __tablename__ = "extracted_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # Set only when S3/MinIO is configured. Key is tenants/{owner}/...
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="licence")
    sarvam_job_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[ExtractionStatus] = mapped_column(
        SAEnum(ExtractionStatus), nullable=False, default=ExtractionStatus.PENDING
    )
    raw_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structured_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    min_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="documents")

    @property
    def low_confidence_fields(self) -> Dict[str, float]:
        """Fields the extractor was unsure about, for reviewer attention."""
        from app.core.document_intelligence import CONFIDENCE_REVIEW_THRESHOLD

        confidence = (self.structured_data or {}).get("confidence") or {}
        return {
            field: score
            for field, score in confidence.items()
            if isinstance(score, (int, float)) and score < CONFIDENCE_REVIEW_THRESHOLD
        }
