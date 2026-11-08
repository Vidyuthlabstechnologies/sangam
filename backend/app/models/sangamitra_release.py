"""Production database models for Sangamitra Release v1.0.0:
- TenantAgentProfile (persisted zero-prompt voice agents & Sarvam bindings)
- TenantWalletModel & WalletLedgerEntryModel (ACID 60/40 wallet & ledger)
- ComposioConnectionModel & ComposioExecutionLogModel (persisted OAuth tools & runs)
- AiSafetyReportModel & AccountDeletionAuditModel (Google Play 2026 & DPDP Act 2023 compliance)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow_naive() -> datetime:
    """Timezone-safe naive UTC timestamp for SQLAlchemy DateTime columns (Python 3.14 clean)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TenantAgentProfile(Base):
    __tablename__ = "tenant_agent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    category_id: Mapped[str] = mapped_column(String(64), nullable=False, default="b2b_manufacturing")
    subcategory: Mapped[str] = mapped_column(String(120), nullable=False, default="General")
    vertical_pack_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mascot_id: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    assigned_did: Mapped[Optional[str]] = mapped_column(String(24), index=True, nullable=True)
    sarvam_app_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sarvam_deployment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    primary_language: Mapped[str] = mapped_column(String(16), nullable=False, default="kn-IN")
    supported_languages: Mapped[list] = mapped_column(JSON, default=list)
    speaker_voice: Mapped[str] = mapped_column(String(32), nullable=False, default="priya")
    pace: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    knowledge_base_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_code_mixed_words: Mapped[list] = mapped_column(JSON, default=list)
    business_hours_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)


class TenantWalletModel(Base):
    __tablename__ = "tenant_wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    assigned_did: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    mascot_id: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    primary_language: Mapped[str] = mapped_column(String(16), nullable=False, default="kn-IN")
    deployment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNPROVISIONED")
    call_balance_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_gross_paid_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_platform_profit_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sarvam_cogs_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_seconds_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upi_autopay_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    upi_autopay_threshold_inr: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    upi_autopay_amount_inr: Mapped[float] = mapped_column(Float, nullable=False, default=299.0)
    referral_code: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="")
    # The logged-in actor who owns this tenant. NULL only for platform-seeded demo tenants.
    owner_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    # Presented as X-Tenant-Key on voice webhooks. The shared webhook secret alone
    # cannot debit this wallet; the key is generated server-side and never logged.
    metering_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    plan_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    plan_valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False)


class WalletOrderModel(Base):
    """A server-priced Razorpay order. Payment verification trusts THIS row, never client-sent amounts."""
    __tablename__ = "wallet_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razorpay_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(48), nullable=False)  # "PLAN:<plan_id>" | "TOPUP"
    base_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    total_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="CREATED")  # CREATED | PAID
    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class WalletLedgerEntryModel(Base):
    __tablename__ = "wallet_ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    gross_amount_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    platform_profit_60_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    backend_pool_40_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    did_allocation_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    call_credit_delta_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    gst_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Sequential GST invoice number for paid entries. UNIQUE so duplicates are impossible.
    invoice_seq: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class ComposioConnectionModel(Base):
    __tablename__ = "composio_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    app_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    connection_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONNECTED")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class ComposioExecutionLogModel(Base):
    __tablename__ = "composio_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    app_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUCCESS")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class AiSafetyReportModel(Base):
    __tablename__ = "ai_safety_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    utterance_flagged: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="LOGGED_FOR_GUARDRAIL_REVIEW")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class AccountDeletionAuditModel(Base):
    __tablename__ = "account_deletion_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DELETED")
    deleted_items_json: Mapped[list] = mapped_column(JSON, default=list)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
