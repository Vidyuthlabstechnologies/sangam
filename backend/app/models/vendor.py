from __future__ import annotations
import uuid
from datetime import datetime, date, timedelta
from enum import Enum
from typing import List, Optional

from sqlalchemy import String, DateTime, Date, Enum as SAEnum, ForeignKey, Text, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class VendorStatus(str, Enum):
    DRAFT = "draft"
    PENDING_QUALIFICATION = "pending_qualification"
    QUALIFIED = "qualified"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


class LicenceType(str, Enum):
    CDSCO = "cdsco"
    STATE_FDA = "state_fda"
    GST = "gst"
    MCA = "mca"
    ISO = "iso"
    WHO_GMP = "who_gmp"


class Vendor(Base):
    """A supplier being qualified to supply a regulated manufacturer.

    Vendors are distinct from Actors: an Actor is a participant in workflows
    (human, agent, system), whereas a Vendor is the organisation being
    assessed. A vendor may have an associated Actor once it is onboarded
    onto the platform, hence the nullable link.
    """

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    legal_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    gstin: Mapped[Optional[str]] = mapped_column(String(15), nullable=True, index=True)
    pan: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[VendorStatus] = mapped_column(
        SAEnum(VendorStatus), nullable=False, default=VendorStatus.DRAFT
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True
    )
    # Actor who registered this vendor. Reads and writes are limited to them.
    owner_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True, index=True
    )
    qualification_workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    licences = relationship(
        "VendorLicence", back_populates="vendor", lazy="selectin",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "ExtractedDocument", back_populates="vendor", lazy="selectin",
    )

    @property
    def has_expired_licence(self) -> bool:
        today = date.today()
        return any(lic.expiry_date and lic.expiry_date < today for lic in self.licences)

    def licences_expiring_within(self, days: int) -> List["VendorLicence"]:
        """Licences lapsing inside the given window.

        Drives the expiry warnings that are the day-to-day value of the
        vendor list: a lapsed CDSCO licence means production stops.
        """
        cutoff = date.today() + timedelta(days=days)
        return [
            lic for lic in self.licences
            if lic.expiry_date and date.today() <= lic.expiry_date <= cutoff
        ]

    @property
    def is_qualifiable(self) -> bool:
        """Whether the vendor has enough verified data to submit for approval."""
        return bool(self.licences) and not self.has_expired_licence


class VendorLicence(Base):
    __tablename__ = "vendor_licences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False
    )
    licence_type: Mapped[LicenceType] = mapped_column(SAEnum(LicenceType), nullable=False)
    licence_number: Mapped[str] = mapped_column(String(128), nullable=False)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Confidence reported by the extraction pipeline. Low values mean a human
    # should confirm the value before it is relied on for a qualification
    # decision.
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="licences")

    @property
    def is_expired(self) -> bool:
        return bool(self.expiry_date and self.expiry_date < date.today())

    @property
    def days_until_expiry(self) -> Optional[int]:
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days
