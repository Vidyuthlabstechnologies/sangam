"""Database-backed prepaid wallet, ledger and GST invoicing for Sangamitra.

Replaces the old in-memory BillingEngine. Everything is integer paise, every
mutation runs inside the caller's transaction with the wallet row locked, and
idempotency comes from the UNIQUE ledger transaction_id: replaying a payment
id or a call id can never credit or debit twice.

Things this deliberately does NOT do:
  * It never creates money. The old engine "auto-topped-up" a wallet from an
    autopay flag without any payment; here autopay is only a stored preference
    until a real Razorpay mandate exists.
  * It never trusts a client-sent amount. Plan and top-up prices come from
    app.core.pricing and the server-created WalletOrderModel row.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pricing
from app.models.sangamitra_release import (
    ComposioConnectionModel,
    TenantWalletModel,
    WalletLedgerEntryModel,
)

SUPPLIER_STATE_CODE = "29"  # Karnataka
REFERRAL_BONUS_PAISE = 10_000
MASCOTS = ("v1", "v2", "v3")

STATUS_UNPROVISIONED = "UNPROVISIONED"
STATUS_ACTIVE = "ACTIVE"
STATUS_PAUSED_ZERO = "PAUSED_ZERO_BALANCE"
STATUS_PLAN_EXPIRED = "PLAN_EXPIRED"

PAYMENT_KINDS = ("PLAN", "TOPUP")
logger = logging.getLogger("sangam.billing")


def usage_transaction_id(call_id: str) -> str:
    """Stable ledger key for one call. The column is VARCHAR(64).

    Short ids stay ``call:{id}`` so rows already written still match.
    Longer ids are hashed; the hash is stable, so a retry hits the same row.
    """
    raw = f"call:{call_id}"
    if len(raw) <= 64:
        return raw
    return "call:" + hashlib.sha256(call_id.encode()).hexdigest()[:32]


class BillingError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _inr(paise: int) -> float:
    return round(paise / 100, 2)


def _fy_label(when: datetime) -> str:
    start = when.year if when.month >= 4 else when.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ wallets
    async def get_wallet(self, tenant_id: str, *, lock: bool = False) -> Optional[TenantWalletModel]:
        stmt = select(TenantWalletModel).where(TenantWalletModel.tenant_id == tenant_id)
        if lock:
            stmt = stmt.with_for_update()
        wallet = (await self.session.execute(stmt)).scalar_one_or_none()
        if (
            wallet is not None
            and not wallet.metering_key
            and wallet.business_name != "Deleted account"
        ):
            wallet.metering_key = secrets.token_urlsafe(32)
        return wallet

    async def get_or_create_wallet(
        self,
        tenant_id: str,
        *,
        owner_actor_id: Optional[uuid.UUID] = None,
        business_name: Optional[str] = None,
        mascot_id: Optional[str] = None,
        primary_language: Optional[str] = None,
        gstin: Optional[str] = None,
        lock: bool = False,
    ) -> TenantWalletModel:
        wallet = await self.get_wallet(tenant_id, lock=lock)
        if wallet is None:
            slug = "".join(ch for ch in tenant_id.upper() if ch.isalnum())[:10] or "NEW"
            wallet = TenantWalletModel(
                tenant_id=tenant_id,
                owner_actor_id=owner_actor_id,
                business_name=business_name or "New Sangamitra Business",
                gstin=gstin,
                mascot_id=mascot_id if mascot_id in MASCOTS else "v1",
                primary_language=primary_language or "kn-IN",
                deployment_status=STATUS_UNPROVISIONED,
                referral_code=f"SANGAM-{slug}-{uuid.uuid4().hex[:4].upper()}",
                metering_key=secrets.token_urlsafe(32),
            )
            self.session.add(wallet)
            try:
                await self.session.flush()
            except IntegrityError:
                # Two first requests raced; the other one won. Use its row.
                await self.session.rollback()
                wallet = await self.get_wallet(tenant_id, lock=lock)
                if wallet is None:
                    raise
        return wallet

    def _refresh_status(self, wallet: TenantWalletModel) -> None:
        """Derive status from plan expiry and balance. Never reactivates an unpaid wallet."""
        if wallet.deployment_status == STATUS_UNPROVISIONED:
            return
        if wallet.plan_valid_until is not None and _now() > wallet.plan_valid_until:
            wallet.deployment_status = STATUS_PLAN_EXPIRED
        elif wallet.call_balance_paise <= 0:
            wallet.deployment_status = STATUS_PAUSED_ZERO
        else:
            wallet.deployment_status = STATUS_ACTIVE

    # ------------------------------------------------------------------- ledger
    async def _ledger_entry(self, transaction_id: str) -> Optional[WalletLedgerEntryModel]:
        stmt = select(WalletLedgerEntryModel).where(WalletLedgerEntryModel.transaction_id == transaction_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _next_invoice_seq(self) -> int:
        current = (await self.session.execute(select(func.max(WalletLedgerEntryModel.invoice_seq)))).scalar()
        return (current or 0) + 1

    async def _add_entry(
        self,
        *,
        wallet: TenantWalletModel,
        transaction_id: str,
        kind: str,
        gross_paise: int = 0,
        gst_paise: int = 0,
        profit_paise: int = 0,
        pool_paise: int = 0,
        did_paise: int = 0,
        credit_delta_paise: int = 0,
        description: str,
        invoiced: bool = False,
    ) -> WalletLedgerEntryModel:
        entry = WalletLedgerEntryModel(
            transaction_id=transaction_id,
            tenant_id=wallet.tenant_id,
            kind=kind,
            gross_amount_inr=_inr(gross_paise),
            gst_inr=_inr(gst_paise),
            platform_profit_60_inr=_inr(profit_paise),
            backend_pool_40_inr=_inr(pool_paise),
            did_allocation_inr=_inr(did_paise),
            call_credit_delta_inr=_inr(credit_delta_paise),
            description=description[:500],
            invoice_seq=(await self._next_invoice_seq()) if invoiced else None,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    # ----------------------------------------------------------------- payments
    async def credit_plan(
        self,
        tenant_id: str,
        plan: pricing.Plan,
        payment_id: str,
        *,
        owner_actor_id: Optional[uuid.UUID] = None,
        business_name: Optional[str] = None,
        mascot_id: Optional[str] = None,
        primary_language: Optional[str] = None,
        gstin: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply a VERIFIED, PAID plan purchase. Safe to call twice with the same payment id."""
        wallet = await self.get_or_create_wallet(
            tenant_id,
            owner_actor_id=owner_actor_id,
            business_name=business_name,
            mascot_id=mascot_id,
            primary_language=primary_language,
            gstin=gstin,
            lock=True,
        )
        if await self._ledger_entry(payment_id) is not None:
            return await self.serialize(wallet, idempotent_replay=True)

        s = pricing.split_plan(plan)
        if business_name:
            wallet.business_name = business_name
        if gstin:
            wallet.gstin = gstin
        if mascot_id in MASCOTS:
            wallet.mascot_id = mascot_id
        if primary_language:
            wallet.primary_language = primary_language

        now = _now()
        # Renewing early extends from the current expiry instead of wasting paid days.
        base_time = wallet.plan_valid_until if wallet.plan_valid_until and wallet.plan_valid_until > now else now
        wallet.plan_id = plan.plan_id
        wallet.plan_valid_until = base_time + timedelta(days=plan.validity_days)
        wallet.call_balance_paise += s.wallet_credit_paise
        wallet.total_gross_paid_paise += s.total_paise
        wallet.total_platform_profit_paise += s.platform_profit_paise
        wallet.total_sarvam_cogs_paise += s.provider_pool_paise
        wallet.deployment_status = STATUS_ACTIVE

        await self._add_entry(
            wallet=wallet,
            transaction_id=payment_id,
            kind="PLAN",
            gross_paise=s.total_paise,
            gst_paise=s.gst_paise,
            profit_paise=s.platform_profit_paise,
            pool_paise=s.provider_pool_paise,
            did_paise=s.did_paise,
            credit_delta_paise=s.wallet_credit_paise,
            description=f"{plan.name} plan ({plan.validity_days} days): about {s.included_minutes} call minutes included",
            invoiced=True,
        )
        return await self.serialize(wallet)

    async def credit_topup(self, tenant_id: str, base_paise: int, payment_id: str) -> Dict[str, Any]:
        """Apply a VERIFIED, PAID top-up. `base_paise` is the ex-GST amount from the server-priced order."""
        wallet = await self.get_wallet(tenant_id, lock=True)
        if wallet is None:
            raise BillingError("Wallet not found", 404)
        if await self._ledger_entry(payment_id) is not None:
            return await self.serialize(wallet, idempotent_replay=True)

        s = pricing.split_topup(base_paise)
        wallet.call_balance_paise += s.wallet_credit_paise
        wallet.total_gross_paid_paise += s.total_paise
        wallet.total_platform_profit_paise += s.platform_profit_paise
        wallet.total_sarvam_cogs_paise += s.provider_pool_paise
        self._refresh_status(wallet)

        await self._add_entry(
            wallet=wallet,
            transaction_id=payment_id,
            kind="TOPUP",
            gross_paise=s.total_paise,
            gst_paise=s.gst_paise,
            profit_paise=s.platform_profit_paise,
            pool_paise=s.provider_pool_paise,
            credit_delta_paise=s.wallet_credit_paise,
            description=f"Wallet recharge Rs. {_inr(base_paise)} plus GST",
            invoiced=True,
        )
        return await self.serialize(wallet)

    async def reverse_payment(self, tenant_id: str, payment_id: str, reversal_id: str) -> Dict[str, Any]:
        """Take back what a refunded PLAN or TOPUP credited. Idempotent on `reversal_id`.

        Removes the call credit the payment added, but never below zero: credit
        already spent on calls cannot be recovered from the wallet. A refunded
        plan also loses the validity days it added. Unknown payment ids are a
        no-op, so a refund for a purchase this server never credited changes nothing.
        """
        wallet = await self.get_wallet(tenant_id, lock=True)
        original = await self._ledger_entry(payment_id)
        if wallet is None or original is None or original.tenant_id != tenant_id:
            return {"status": "not_found", "reversed_paise": 0}
        if original.kind not in PAYMENT_KINDS:
            raise BillingError("Only plan and top-up payments can be reversed", 400)
        if await self._ledger_entry(reversal_id) is not None:
            res = await self.serialize(wallet, idempotent_replay=True)
            res["status"] = "already_reversed"
            return res

        credited = int(round(original.call_credit_delta_inr * 100))
        gross = int(round(original.gross_amount_inr * 100))
        profit = int(round(original.platform_profit_60_inr * 100))
        pool = int(round(original.backend_pool_40_inr * 100))
        taken = min(max(credited, 0), max(wallet.call_balance_paise, 0))
        wallet.call_balance_paise -= taken
        wallet.total_gross_paid_paise = max(wallet.total_gross_paid_paise - gross, 0)
        wallet.total_platform_profit_paise = max(wallet.total_platform_profit_paise - profit, 0)
        wallet.total_sarvam_cogs_paise = max(wallet.total_sarvam_cogs_paise - pool, 0)

        if original.kind == "PLAN" and wallet.plan_valid_until is not None:
            plan = pricing.get_plan(wallet.plan_id or "")
            if plan is not None:
                cut = wallet.plan_valid_until - timedelta(days=plan.validity_days)
                # A plan with no paid days left expires now instead of running on.
                wallet.plan_valid_until = cut if cut > _now() else _now() - timedelta(seconds=1)
        self._refresh_status(wallet)

        note = f"Refund of {original.kind.lower()} payment {payment_id}"
        if taken < credited:
            note += f" (Rs. {_inr(credited - taken)} already spent on calls, not recoverable)"
        await self._add_entry(
            wallet=wallet,
            transaction_id=reversal_id,
            kind="REFUND",
            gross_paise=-gross,
            gst_paise=-int(round(original.gst_inr * 100)),
            profit_paise=-profit,
            pool_paise=-pool,
            credit_delta_paise=-taken,
            description=note,
        )
        logger.warning(
            "payment reversed",
            extra={"tenant_id": tenant_id, "payment_id": payment_id, "taken_paise": taken, "credited_paise": credited},
        )
        res = await self.serialize(wallet)
        res["status"] = "reversed"
        res["reversed_paise"] = taken
        res["unrecovered_paise"] = credited - taken
        return res

    # ------------------------------------------------------------------- usage
    async def meter_call(self, tenant_id: str, duration_seconds: int, call_id: Optional[str]) -> Dict[str, Any]:
        """Debit a finished call. Idempotent per call id. The balance never goes below zero.

        A missing call id is not debited. A random ledger key would charge
        again on every webhook retry. The unique transaction id is the
        backstop when two retries pass the existence check together: the
        loser hits IntegrityError, the transaction rolls back, and the
        committed balance is the one from the first insert.
        """
        wallet = await self.get_or_create_wallet(tenant_id, lock=True)
        call_key = (call_id or "").strip()
        if not call_key:
            logger.warning("Skipping call debit because call_id is missing")
            res = await self.serialize(wallet)
            res["last_call_debit_inr"] = 0.0
            res["debit_skipped"] = "call_id_required"
            return res

        txn_id = usage_transaction_id(call_key)
        existing = await self._ledger_entry(txn_id)
        if existing is not None:
            res = await self.serialize(wallet, idempotent_replay=True)
            res["circuit_breaker_triggered"] = wallet.deployment_status == STATUS_PAUSED_ZERO
            return res

        wanted = pricing.call_debit_paise(duration_seconds)
        debit = min(wanted, wallet.call_balance_paise)
        raw_cost = pricing.call_raw_cost_paise(duration_seconds)

        wallet.call_balance_paise -= debit
        wallet.total_seconds_consumed += max(int(duration_seconds), 1)
        self._refresh_status(wallet)

        note = f"Voice call {int(duration_seconds)}s"
        if debit < wanted:
            note += f" (balance ran out: Rs. {_inr(wanted - debit)} not recoverable)"
        try:
            await self._add_entry(
                wallet=wallet,
                transaction_id=txn_id,
                kind="CALL_USAGE",
                gross_paise=debit,
                profit_paise=max(debit - raw_cost, 0),
                pool_paise=raw_cost,
                credit_delta_paise=-debit,
                description=note,
            )
        except IntegrityError:
            await self.session.rollback()
            wallet = await self.get_or_create_wallet(tenant_id, lock=True)
            res = await self.serialize(wallet, idempotent_replay=True)
            res["circuit_breaker_triggered"] = wallet.deployment_status == STATUS_PAUSED_ZERO
            return res
        res = await self.serialize(wallet)
        res["last_call_debit_inr"] = _inr(debit)
        res["last_call_provider_cost_inr"] = _inr(raw_cost)
        res["circuit_breaker_triggered"] = wallet.deployment_status == STATUS_PAUSED_ZERO
        res["low_balance_alert"] = wallet.call_balance_paise <= 5000
        res["autopay_charge_needed"] = bool(
            wallet.upi_autopay_enabled and wallet.call_balance_paise < int(wallet.upi_autopay_threshold_inr * 100)
        )
        return res

    # ----------------------------------------------------------------- settings
    async def configure_autopay(
        self, tenant_id: str, enabled: bool, threshold_inr: float, amount_inr: float
    ) -> Dict[str, Any]:
        """Stores the preference only. No mandate exists, so nothing is ever charged or credited from this."""
        wallet = await self.get_wallet(tenant_id, lock=True)
        if wallet is None:
            raise BillingError("Wallet not found", 404)
        if not (0 <= threshold_inr <= 10_000) or not (pricing.MIN_TOPUP_PAISE / 100 <= amount_inr <= pricing.MAX_TOPUP_PAISE / 100):
            raise BillingError("Autopay amounts out of range")
        wallet.upi_autopay_enabled = enabled
        wallet.upi_autopay_threshold_inr = threshold_inr
        wallet.upi_autopay_amount_inr = amount_inr
        res = await self.serialize(wallet)
        res["mandate_status"] = "NOT_CONNECTED"
        return res

    async def apply_referral(self, tenant_id: str, referral_code: str) -> Dict[str, Any]:
        """Rs. 100 talktime to both sides, once per tenant, only after the claimer has paid for a plan."""
        wallet = await self.get_wallet(tenant_id, lock=True)
        if wallet is None or wallet.total_gross_paid_paise <= 0:
            raise BillingError("Referral bonus unlocks after your first paid plan", 409)
        code = (referral_code or "").strip().upper()
        referrer = (
            await self.session.execute(
                select(TenantWalletModel)
                .where(TenantWalletModel.referral_code == code, TenantWalletModel.tenant_id != tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if referrer is None:
            raise BillingError("Invalid referral code", 404)
        claim_id = f"refclaim:{tenant_id}"
        if await self._ledger_entry(claim_id) is not None:
            raise BillingError("Referral bonus already claimed", 409)

        for w, txn in ((wallet, claim_id), (referrer, f"refgive:{referrer.tenant_id}:{tenant_id}")):
            w.call_balance_paise += REFERRAL_BONUS_PAISE
            # The credit costs us real provider money (raw cost = 40% of retail value).
            cost = REFERRAL_BONUS_PAISE * pricing.PROVIDER_POOL_PCT // 100
            w.total_platform_profit_paise -= cost
            self._refresh_status(w)
            await self._add_entry(
                wallet=w,
                transaction_id=txn,
                kind="REFERRAL",
                profit_paise=-cost,
                credit_delta_paise=REFERRAL_BONUS_PAISE,
                description="Referral bonus Rs. 100 talktime",
            )
        return {
            "tenant_id": tenant_id,
            "referrer_tenant_id": referrer.tenant_id,
            "bonus_credited_inr": _inr(REFERRAL_BONUS_PAISE),
            "new_tenant_balance_inr": _inr(wallet.call_balance_paise),
        }

    # ----------------------------------------------------------------- reporting
    async def invoices(self, tenant_id: str) -> List[Dict[str, Any]]:
        wallet = await self.get_wallet(tenant_id)
        if wallet is None:
            raise BillingError("Wallet not found", 404)
        rows = (
            await self.session.execute(
                select(WalletLedgerEntryModel)
                .where(WalletLedgerEntryModel.tenant_id == tenant_id, WalletLedgerEntryModel.invoice_seq.is_not(None))
                .order_by(WalletLedgerEntryModel.invoice_seq)
            )
        ).scalars().all()
        gstin = (wallet.gstin or "").strip().upper()
        intra = not gstin or gstin.startswith(SUPPLIER_STATE_CODE)
        out = []
        for r in rows:
            gst = round(r.gst_inr, 2)
            half = round(gst / 2, 2)
            out.append(
                {
                    "invoice_number": f"SGM/{_fy_label(r.created_at)}/{r.invoice_seq:05d}",
                    "invoice_date": r.created_at.strftime("%Y-%m-%d"),
                    "supplier_name": "Sangamitra AI Voice Technologies",
                    "supplier_state_code": SUPPLIER_STATE_CODE,
                    "sac_code": "998315",
                    "customer_name": wallet.business_name,
                    "customer_gstin": gstin or "UNREGISTERED",
                    "supply_type": "INTRA_STATE_CGST_SGST" if intra else "INTER_STATE_IGST",
                    "description": r.description,
                    "taxable_amount_inr": round(r.gross_amount_inr - gst, 2),
                    "cgst_9_pct_inr": half if intra else 0.0,
                    "sgst_9_pct_inr": round(gst - half, 2) if intra else 0.0,
                    "igst_18_pct_inr": 0.0 if intra else gst,
                    "total_gross_inr": round(r.gross_amount_inr, 2),
                    "payment_reference": r.transaction_id,
                    "status": "PAID",
                }
            )
        return out

    async def platform_summary(self) -> Dict[str, Any]:
        row = (
            await self.session.execute(
                select(
                    func.count(TenantWalletModel.id),
                    func.coalesce(func.sum(TenantWalletModel.total_gross_paid_paise), 0),
                    func.coalesce(func.sum(TenantWalletModel.total_platform_profit_paise), 0),
                    func.coalesce(func.sum(TenantWalletModel.total_sarvam_cogs_paise), 0),
                    func.coalesce(func.sum(TenantWalletModel.total_seconds_consumed), 0),
                )
            )
        ).one()
        by_status = dict(
            (await self.session.execute(
                select(TenantWalletModel.deployment_status, func.count(TenantWalletModel.id))
                .group_by(TenantWalletModel.deployment_status)
            )).all()
        )
        gross, profit, pool = int(row[1]), int(row[2]), int(row[3])
        return {
            "total_tenants": int(row[0]),
            "active_deployments": by_status.get(STATUS_ACTIVE, 0),
            "paused_zero_balance_deployments": by_status.get(STATUS_PAUSED_ZERO, 0),
            "plan_expired_deployments": by_status.get(STATUS_PLAN_EXPIRED, 0),
            "total_collected_incl_gst_inr": _inr(gross),
            "total_platform_net_profit_inr": _inr(profit),
            "total_provider_pool_inr": _inr(pool),
            "total_minutes_consumed": round(int(row[4]) / 60, 2),
            "profit_pct_of_ex_gst_revenue": round(100 * profit / (pool + profit), 2) if (pool + profit) else 0.0,
        }

    # ------------------------------------------------------------------ account
    async def delete_tenant(self, tenant_id: str) -> List[str]:
        """Remove personal data. Ledger rows are kept: Indian GST law requires 6 years of invoice records,
        so they are detached from the business name instead of deleted."""
        deleted: List[str] = []
        wallet = await self.get_wallet(tenant_id, lock=True)
        if wallet is not None:
            wallet.business_name = "Deleted account"
            wallet.gstin = None
            wallet.assigned_did = None
            wallet.owner_actor_id = None
            wallet.metering_key = None
            wallet.upi_autopay_enabled = False
            wallet.deployment_status = STATUS_PAUSED_ZERO
            wallet.call_balance_paise = 0
            deleted += ["wallet_profile", "assigned_did_binding"]
        conns = (
            await self.session.execute(
                select(ComposioConnectionModel).where(ComposioConnectionModel.tenant_id == tenant_id)
            )
        ).scalars().all()
        for c in conns:
            await self.session.delete(c)
        if conns:
            deleted.append("tool_connections")
        return deleted

    # ------------------------------------------------------------------ output
    async def serialize(self, wallet: TenantWalletModel, *, idempotent_replay: bool = False) -> Dict[str, Any]:
        self._refresh_status(wallet)
        recent = (
            await self.session.execute(
                select(WalletLedgerEntryModel)
                .where(WalletLedgerEntryModel.tenant_id == wallet.tenant_id)
                .order_by(WalletLedgerEntryModel.created_at.desc(), WalletLedgerEntryModel.invoice_seq.desc())
                .limit(20)
            )
        ).scalars().all()
        bal = wallet.call_balance_paise
        out = {
            "tenant_id": wallet.tenant_id,
            "business_name": wallet.business_name,
            "gstin": wallet.gstin,
            "assigned_did": wallet.assigned_did,
            "mascot_id": wallet.mascot_id,
            "primary_language": wallet.primary_language,
            "deployment_status": wallet.deployment_status,
            "plan_id": wallet.plan_id,
            "plan_valid_until": wallet.plan_valid_until.isoformat() if wallet.plan_valid_until else None,
            "call_balance_inr": _inr(bal),
            "estimated_remaining_minutes": bal // pricing.RETAIL_RATE_PER_MIN_PAISE,
            "max_allowed_call_seconds": bal * 60 // pricing.RETAIL_RATE_PER_MIN_PAISE,
            "customer_rate_per_min_inr": _inr(pricing.RETAIL_RATE_PER_MIN_PAISE),
            "total_paid_incl_gst_inr": _inr(wallet.total_gross_paid_paise),
            "total_minutes_consumed": round(wallet.total_seconds_consumed / 60, 2),
            "upi_autopay_enabled": wallet.upi_autopay_enabled,
            "upi_autopay_threshold_inr": wallet.upi_autopay_threshold_inr,
            "upi_autopay_amount_inr": wallet.upi_autopay_amount_inr,
            "referral_code": wallet.referral_code,
            "metering_key": wallet.metering_key,
            "transactions": [
                {
                    "transaction_id": r.transaction_id,
                    "kind": r.kind,
                    "amount_inr": r.gross_amount_inr,
                    "gst_inr": r.gst_inr,
                    "call_credit_delta_inr": r.call_credit_delta_inr,
                    "description": r.description,
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent
            ],
        }
        if idempotent_replay:
            out["idempotent_replay"] = True
        return out


async def seed_live_tenants(session: AsyncSession) -> None:
    """Create wallets for the two already-deployed demo agents if they don't exist.

    They are platform-owned (no owner_actor_id), start ACTIVE with a comped
    balance recorded in the ledger, and carry no invented GSTINs.

    Production refuses this. Those wallets are pilot fixtures, not customer
    accounts that should appear on a live shared deployment at boot.
    """
    from app.config import settings

    if settings.environment.strip().lower() == "production":
        raise RuntimeError("Refusing to seed live pilot wallets in production")
    svc = BillingService(session)
    seeds = (
        ("abhishek-industries", "Abhishek Industries (Tumakuru)", "+918064270314", "v3", "kn-IN"),
        ("surya-enterprises", "Surya Enterprises (Hyderabad)", "+918064270306", "v1", "te-IN"),
    )
    for tenant_id, name, did, mascot, lang in seeds:
        if await svc.get_wallet(tenant_id) is not None:
            continue
        wallet = await svc.get_or_create_wallet(
            tenant_id, business_name=name, mascot_id=mascot, primary_language=lang, lock=True
        )
        wallet.assigned_did = did
        wallet.call_balance_paise = 100_000
        wallet.deployment_status = STATUS_ACTIVE
        await svc._add_entry(
            wallet=wallet,
            transaction_id=f"seed:{tenant_id}",
            kind="COMP_CREDIT",
            credit_delta_paise=100_000,
            description="Platform-granted opening balance for a pilot tenant",
        )
    await session.commit()
