from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, DateTime, Enum as SAEnum, JSON, ForeignKey, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base import Base


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=True)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True)
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING)
    method: Mapped[Optional[PaymentMethod]] = mapped_column(SAEnum(PaymentMethod), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payer_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True)
    payee_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("actors.id"), nullable=True)
    extra_attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column("extra_attributes", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow")
    payer = relationship("Actor", foreign_keys=[payer_actor_id])
    payee = relationship("Actor", foreign_keys=[payee_actor_id])


class EscrowStatus(str, Enum):
    HELD = "held"
    RELEASED = "released"
    DISPUTED = "disputed"
    REFUNDED = "refunded"
    PARTIALLY_RELEASED = "partially_released"


class Escrow(Base):
    __tablename__ = "escrows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    payment_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[EscrowStatus] = mapped_column(SAEnum(EscrowStatus), nullable=False, default=EscrowStatus.HELD)
    release_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    release_trigger: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow")
    payment = relationship("Payment")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    payment_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payer_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payer_gst: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    payee_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    payee_gst: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
