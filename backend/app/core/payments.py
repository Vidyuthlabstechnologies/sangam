from __future__ import annotations
import uuid
import hmac
import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

import razorpay
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core import fixtures
from app.core.money import parse_amount, to_minor_units
from app.models.payment import (
    Payment, PaymentStatus, PaymentMethod,
    Escrow, EscrowStatus,
    Invoice,
)
from app.core.audit import AuditService


logger = logging.getLogger("sangam.payments")


class RazorpayService:
    def __init__(self):
        key_id = settings.razorpay_key_id
        key_secret = settings.razorpay_key_secret

        # Absent credentials mean fixture mode, not a hard failure. This is
        # deliberate for payments specifically: escrow release is automatic,
        # so development and tests must never be able to reach a live
        # gateway by accident.
        self.use_fixtures = settings.use_fixtures or not (key_id and key_secret)
        self.client = None if self.use_fixtures else razorpay.Client(auth=(key_id, key_secret))

    async def create_order(
        self,
        amount: float,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        amount_paise = to_minor_units(amount)
        receipt_id = receipt or str(uuid.uuid4())
        if self.use_fixtures:
            return fixtures.razorpay_order(amount_paise, receipt_id)

        order_data = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt_id,
            "notes": notes or {},
        }
        order = self.client.order.create(order_data)
        return order

    async def capture_payment(
        self,
        payment_id: str,
        amount: float,
    ) -> Dict[str, Any]:
        amount_paise = to_minor_units(amount)
        if self.use_fixtures:
            return fixtures.razorpay_payment(payment_id)
        return self.client.payment.capture(payment_id, amount_paise)

    async def verify_payment(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        secret = settings.razorpay_key_secret
        if not secret:
            # Fail closed: no secret means nothing can be verified, and a
            # missing setting must be a rejection, not a 500.
            logger.error("Cannot verify a payment signature: RAZORPAY_KEY_SECRET is not set")
            return False
        expected = hmac.new(
            secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
        """Verify a Razorpay webhook against its HMAC-SHA256 signature.

        The signature covers the exact raw request bytes, so callers must
        pass the unparsed body — re-serialising the JSON changes key order
        and whitespace, which invalidates the digest.

        Returns False when no webhook secret is configured: an unverifiable
        webhook is not a trusted one.
        """
        secret = settings.razorpay_webhook_secret
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        if self.use_fixtures:
            return fixtures.razorpay_refund(payment_id)

        params = {}
        if amount is not None:
            params["amount"] = to_minor_units(amount)
        return self.client.payment.refund(payment_id, params)

    async def get_payment_details(self, payment_id: str) -> Dict[str, Any]:
        if self.use_fixtures:
            return fixtures.razorpay_payment(payment_id)
        return self.client.payment.fetch(payment_id)

    async def create_upi_intent_order(
        self,
        amount: float,
        upi_id: Optional[str] = None,
        currency: str = "INR",
        receipt: Optional[str] = None,
    ) -> Dict[str, Any]:
        amount_paise = to_minor_units(amount)
        receipt_id = receipt or str(uuid.uuid4())
        if self.use_fixtures:
            return fixtures.razorpay_order(amount_paise, receipt_id, upi=True)

        # Razorpay's Orders API takes `method` as a STRING. The previous
        # implementation sent {"upi": {"flow": "intent"}}, which the API
        # rejects with "expected string but provided object" - the UPI
        # intent flow and VPA are checkout-time options on the client SDK,
        # not properties of the order.
        order_data: Dict[str, Any] = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt_id,
            "method": "upi",
        }
        notes = {"upi_flow": "intent"}
        if upi_id:
            notes["vpa"] = upi_id
        order_data["notes"] = notes

        order = self.client.order.create(order_data)
        return order

    async def create_invoice(
        self,
        amount: float,
        description: str,
        payer_name: Optional[str] = None,
        payer_email: Optional[str] = None,
        payer_contact: Optional[str] = None,
        currency: str = "INR",
    ) -> Dict[str, Any]:
        invoice_data = {
            "type": "invoice",
            "amount": to_minor_units(amount),
            "currency": currency,
            "description": description,
            "customer": {},
        }
        if payer_name:
            invoice_data["customer"]["name"] = payer_name
        if payer_email:
            invoice_data["customer"]["email"] = payer_email
        if payer_contact:
            invoice_data["customer"]["contact"] = payer_contact

        return self.client.invoice.create(invoice_data)


class PaymentManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.razorpay = RazorpayService()
        self.audit = AuditService(session)

    async def initiate_payment(
        self,
        workflow_id: UUID,
        amount: float,
        currency: str = "INR",
        description: Optional[str] = None,
        payer_actor_id: Optional[UUID] = None,
        payee_actor_id: Optional[UUID] = None,
        method: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Validate before anything is stored: raises InvalidAmount (a ValueError).
        amount = float(parse_amount(amount))
        payment = Payment(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            amount=amount,
            currency=currency,
            status=PaymentStatus.PENDING,
            description=description,
            payer_actor_id=payer_actor_id,
            payee_actor_id=payee_actor_id,
        )
        self.session.add(payment)
        await self.session.commit()

        if method == "upi_intent":
            order = await self.razorpay.create_upi_intent_order(
                amount=amount,
                currency=currency,
                receipt=str(payment.id),
            )
        else:
            order = await self.razorpay.create_order(
                amount=amount,
                currency=currency,
                receipt=str(payment.id),
            )

        payment.razorpay_order_id = order["id"]
        payment.status = PaymentStatus.PROCESSING
        await self.session.commit()

        await self.audit.log(
            action="payment_initiated",
            resource_type="payment",
            resource_id=str(payment.id),
            workflow_id=workflow_id,
            details={
                "amount": amount,
                "currency": currency,
                "method": method,
                "razorpay_order_id": order["id"],
            },
        )

        return {
            "payment_id": str(payment.id),
            "razorpay_order_id": order["id"],
            "amount": amount,
            "currency": currency,
            "razorpay_key_id": settings.razorpay_key_id,
        }

    async def verify_and_capture(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> Payment:
        valid = await self.razorpay.verify_payment(
            razorpay_order_id, razorpay_payment_id, razorpay_signature
        )
        if not valid:
            raise ValueError("Payment signature verification failed")

        result = await self.session.execute(
            select(Payment).where(Payment.razorpay_order_id == razorpay_order_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise ValueError("Payment not found")

        payment.razorpay_payment_id = razorpay_payment_id
        payment.status = PaymentStatus.CAPTURED

        try:
            details = await self.razorpay.get_payment_details(razorpay_payment_id)
            method_raw = details.get("method", "")
            if method_raw == "upi":
                payment.method = PaymentMethod.UPI
            elif method_raw == "card":
                payment.method = PaymentMethod.CARD
            elif method_raw == "netbanking":
                payment.method = PaymentMethod.NETBANKING
        except Exception:
            # The method is informational; the signature already verified.
            logger.warning("Could not fetch payment method for %s", razorpay_payment_id, exc_info=True)

        await self.session.commit()
        await self.session.refresh(payment)

        await self.audit.log(
            action="payment_captured",
            resource_type="payment",
            resource_id=str(payment.id),
            details={"razorpay_payment_id": razorpay_payment_id},
        )

        return payment

    async def create_escrow(
        self,
        workflow_id: UUID,
        payment_id: UUID,
        amount: float,
        release_condition: Optional[str] = None,
    ) -> Escrow:
        amount = float(parse_amount(amount))
        payment = await self.session.get(Payment, payment_id)
        if payment is None:
            raise ValueError("Payment not found")
        if payment.workflow_id != workflow_id:
            raise ValueError("Payment does not belong to this workflow")
        if amount > payment.amount:
            raise ValueError("Escrow amount cannot exceed the payment amount")

        escrow = Escrow(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            payment_id=payment_id,
            amount=amount,
            status=EscrowStatus.HELD,
            release_condition=release_condition,
        )
        self.session.add(escrow)
        await self.session.commit()
        await self.session.refresh(escrow)

        await self.audit.log(
            action="escrow_created",
            resource_type="escrow",
            resource_id=str(escrow.id),
            workflow_id=workflow_id,
            details={"amount": amount, "release_condition": release_condition},
        )

        return escrow

    async def release_escrow(
        self,
        escrow_id: UUID,
        release_trigger: Optional[str] = None,
    ) -> Escrow:
        result = await self.session.execute(
            select(Escrow)
            .where(Escrow.id == escrow_id)
            .with_for_update()
            # The route has usually loaded this row already. Without
            # populate_existing the ORM hands back that stale object and the
            # status check below reads old data even after waiting for the lock.
            .execution_options(populate_existing=True)
        )
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError("Escrow not found")
        if escrow.status != EscrowStatus.HELD:
            raise ValueError(f"Escrow is {escrow.status.value}")

        payment = await self.session.get(Payment, escrow.payment_id)
        if payment and payment.razorpay_payment_id:
            # Capture FIRST, record after. Marking the escrow released before
            # this call left a dirty RELEASED status on the session whenever
            # the gateway failed, and the next commit persisted it. If the
            # commit below fails after a successful capture, funds have moved
            # without a record; the gateway rejecting a second capture of the
            # same payment is the backstop.
            try:
                await self.razorpay.capture_payment(
                    payment.razorpay_payment_id, escrow.amount
                )
            except Exception as e:
                logger.exception("Gateway capture failed for escrow %s", escrow.id)
                raise ValueError("Failed to capture payment at the gateway") from e

        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = datetime.utcnow()
        escrow.release_trigger = release_trigger
        await self.session.commit()
        await self.session.refresh(escrow)

        await self.audit.log(
            action="escrow_released",
            resource_type="escrow",
            resource_id=str(escrow.id),
            details={"release_trigger": release_trigger},
        )

        return escrow

    async def dispute_escrow(
        self, escrow_id: UUID, actor_id: Optional[UUID] = None
    ) -> Escrow:
        result = await self.session.execute(
            select(Escrow)
            .where(Escrow.id == escrow_id)
            .with_for_update()
            # The route has usually loaded this row already. Without
            # populate_existing the ORM hands back that stale object and the
            # status check below reads old data even after waiting for the lock.
            .execution_options(populate_existing=True)
        )
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError("Escrow not found")
        if escrow.status != EscrowStatus.HELD:
            raise ValueError(f"Escrow is {escrow.status.value}")
        escrow.status = EscrowStatus.DISPUTED
        await self.session.commit()
        await self.session.refresh(escrow)

        await self.audit.log(
            action="escrow_disputed",
            resource_type="escrow",
            resource_id=str(escrow.id),
            actor_id=actor_id,
            workflow_id=escrow.workflow_id,
        )
        return escrow

    async def refund_payment(
        self,
        payment: Payment,
        amount: Optional[float] = None,
        actor_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Refund a captured payment, in full or in part.

        The cumulative refunded amount is not tracked on the model, so a
        second partial refund is bounded by the gateway, not here.
        """
        if (
            payment.status not in (PaymentStatus.CAPTURED, PaymentStatus.PARTIALLY_REFUNDED)
            or not payment.razorpay_payment_id
        ):
            raise ValueError("Only a captured payment can be refunded")

        paid = Decimal(str(payment.amount))
        # Cumulative total lives in the existing extra_attributes JSON, so no
        # schema change is needed. It is always re-assigned as a NEW dict:
        # in-place edits to JSON columns are invisible to SQLAlchemy.
        already = Decimal(str((payment.extra_attributes or {}).get("refunded_amount", "0")))
        remaining = paid - already
        refund_amount = parse_amount(amount) if amount is not None else remaining
        if refund_amount > remaining:
            raise ValueError("Refund cannot exceed the amount still refundable")
        is_full = already + refund_amount == paid

        # Refund policy: funds that were released or are under dispute are
        # settled elsewhere, and held funds can only be returned whole.
        escrows = list(
            (
                await self.session.execute(
                    select(Escrow)
                    .where(Escrow.payment_id == payment.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        )
        for escrow in escrows:
            if escrow.status in (
                EscrowStatus.RELEASED,
                EscrowStatus.DISPUTED,
                EscrowStatus.PARTIALLY_RELEASED,
            ):
                raise ValueError(
                    f"Cannot refund while an escrow is {escrow.status.value}; resolve it first"
                )
            if escrow.status == EscrowStatus.HELD and not is_full:
                raise ValueError("Only a full refund is allowed while escrow funds are held")

        send_amount = None if (amount is None and already == 0) else float(refund_amount)
        refund = await self.razorpay.refund_payment(payment.razorpay_payment_id, send_amount)

        payment.extra_attributes = {
            **(payment.extra_attributes or {}),
            "refunded_amount": str(already + refund_amount),
        }
        payment.status = PaymentStatus.REFUNDED if is_full else PaymentStatus.PARTIALLY_REFUNDED
        if is_full:
            for escrow in escrows:
                if escrow.status == EscrowStatus.HELD:
                    escrow.status = EscrowStatus.REFUNDED
        await self.session.commit()

        await self.audit.log(
            action="payment_refunded",
            resource_type="payment",
            resource_id=str(payment.id),
            actor_id=actor_id,
            workflow_id=payment.workflow_id,
            details={"amount": float(refund_amount), "refund_id": refund.get("id")},
        )
        return refund

    async def create_invoice(
        self,
        workflow_id: UUID,
        payment_id: UUID,
        amount: float,
        description: Optional[str] = None,
        tax_amount: float = 0.0,
        payer_name: Optional[str] = None,
        payer_gst: Optional[str] = None,
        payee_name: Optional[str] = None,
        payee_gst: Optional[str] = None,
    ) -> Invoice:
        amount_d = parse_amount(amount)
        tax_d = parse_amount(tax_amount, allow_zero=True)

        # COUNT instead of loading every invoice. invoice_number is UNIQUE, so
        # two concurrent invoices that read the same count collide on insert;
        # retry with the next number rather than failing the request.
        count = (
            await self.session.execute(select(func.count()).select_from(Invoice))
        ).scalar_one()
        month = datetime.utcnow().strftime("%Y%m")

        for attempt in range(3):
            invoice = Invoice(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                payment_id=payment_id,
                invoice_number=f"INV-{month}-{count + 1 + attempt:05d}",
                amount=float(amount_d),
                tax_amount=float(tax_d),
                total_amount=float(amount_d + tax_d),
                description=description,
                payer_name=payer_name,
                payer_gst=payer_gst,
                payee_name=payee_name,
                payee_gst=payee_gst,
            )
            self.session.add(invoice)
            try:
                await self.session.commit()
            except IntegrityError:
                await self.session.rollback()
                continue
            await self.session.refresh(invoice)
            return invoice
        raise ValueError("Could not allocate an invoice number; please retry")

    async def handle_webhook(self, event: str, payload: dict) -> None:
        """Handle Razorpay webhook events"""
        payment_id = payload.get("payment", {}).get("entity", {}).get("id")
        order_id = payload.get("payment", {}).get("entity", {}).get("order_id")
        
        if not payment_id:
            return
        
        result = await self.session.execute(
            select(Payment).where(Payment.razorpay_payment_id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return
        
        # Webhooks can arrive late or out of order; only an in-flight payment
        # may move on, so a stale "captured" cannot undo a refund.
        in_flight = payment.status in (PaymentStatus.PENDING, PaymentStatus.PROCESSING)
        if event == "payment.captured" and in_flight:
            payment.status = PaymentStatus.CAPTURED
        elif event == "payment.failed" and in_flight:
            payment.status = PaymentStatus.FAILED
        
        await self.session.commit()
