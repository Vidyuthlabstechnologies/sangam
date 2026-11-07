"""Payment, escrow, invoice and webhook endpoints.

Authorization model (see app.core.payment_access): the payer and the
workflow initiator CONTROL a payment, the payee can additionally view and
dispute, and anyone else gets 404 so a payment's existence is not revealed.
"""
import json
import logging
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.core.payment_access import PaymentAccess, payment_access, workflow_initiator
from app.core.payments import PaymentManager, RazorpayService
from app.db.session import get_session
from app.models.actor import Actor
from app.models.payment import Escrow, Invoice, Payment

router = APIRouter(prefix="/payments", tags=["payments"])

logger = logging.getLogger("sangam.payments")

PositiveAmount = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeAmount = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class InitiatePaymentRequest(BaseModel):
    workflow_id: UUID
    amount: PositiveAmount
    currency: str = "INR"
    description: Optional[str] = None
    payer_actor_id: Optional[UUID] = None
    payee_actor_id: Optional[UUID] = None
    method: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class CreateEscrowRequest(BaseModel):
    workflow_id: UUID
    payment_id: UUID
    amount: PositiveAmount
    release_condition: Optional[str] = None


class CreateInvoiceRequest(BaseModel):
    workflow_id: UUID
    payment_id: UUID
    amount: PositiveAmount
    description: Optional[str] = None
    tax_amount: NonNegativeAmount = 0.0
    payer_name: Optional[str] = None
    payer_gst: Optional[str] = None
    payee_name: Optional[str] = None
    payee_gst: Optional[str] = None


# ------------------------------------------------------------- authorization


def _enforce(access: PaymentAccess, actor: Actor, *, control: bool, not_found: str) -> None:
    if not access.can_view(actor.id):
        raise HTTPException(status_code=404, detail=not_found)
    if control and not access.can_control(actor.id):
        raise HTTPException(status_code=403, detail="Not permitted to perform this action")


async def _payment_for(
    session: AsyncSession, payment_id: UUID, actor: Actor, *, control: bool = False
) -> Payment:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    _enforce(await payment_access(session, payment), actor, control=control, not_found="Payment not found")
    return payment


async def _escrow_for(
    session: AsyncSession, escrow_id: UUID, actor: Actor, *, control: bool = False
) -> Escrow:
    escrow = await session.get(Escrow, escrow_id)
    if escrow is None:
        raise HTTPException(status_code=404, detail="Escrow not found")
    payment = await session.get(Payment, escrow.payment_id)
    if payment is not None:
        access = await payment_access(session, payment)
    else:
        initiator = await workflow_initiator(session, escrow.workflow_id)
        ids = frozenset({initiator}) if initiator else frozenset()
        access = PaymentAccess(controllers=ids, viewers=ids)
    _enforce(access, actor, control=control, not_found="Escrow not found")
    return escrow


# ------------------------------------------------------------------- payments


@router.post("/initiate", response_model=dict, status_code=201)
async def initiate_payment(
    req: InitiatePaymentRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    initiator = await workflow_initiator(session, req.workflow_id)
    if initiator is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if initiator != current_actor.id:
        raise HTTPException(status_code=403, detail="Only the workflow initiator can start a payment")

    try:
        return await PaymentManager(session).initiate_payment(
            workflow_id=req.workflow_id,
            amount=req.amount,
            currency=req.currency,
            description=req.description,
            payer_actor_id=req.payer_actor_id or current_actor.id,
            payee_actor_id=req.payee_actor_id,
            method=req.method,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify", response_model=dict)
async def verify_payment(
    req: VerifyPaymentRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    result = await session.execute(
        select(Payment).where(Payment.razorpay_order_id == req.razorpay_order_id)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    _enforce(await payment_access(session, existing), current_actor, control=True, not_found="Payment not found")

    try:
        payment = await PaymentManager(session).verify_and_capture(
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "payment_id": str(payment.id),
        "status": payment.status.value,
        "method": payment.method.value if payment.method else None,
    }


@router.get("/{payment_id}", response_model=dict)
async def get_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    payment = await _payment_for(session, payment_id, current_actor)
    return {
        "id": str(payment.id),
        "workflow_id": str(payment.workflow_id) if payment.workflow_id else None,
        "razorpay_order_id": payment.razorpay_order_id,
        "razorpay_payment_id": payment.razorpay_payment_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status.value,
        "method": payment.method.value if payment.method else None,
        "created_at": payment.created_at.isoformat(),
    }


@router.post("/{payment_id}/refund", response_model=dict)
async def refund_payment(
    payment_id: UUID,
    amount: Optional[float] = Query(None, gt=0, allow_inf_nan=False),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    payment = await _payment_for(session, payment_id, current_actor, control=True)
    try:
        refund = await PaymentManager(session).refund_payment(
            payment, amount, actor_id=current_actor.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # Gateway text can contain request details; log it, do not return it.
        logger.exception("Refund of payment %s failed at the gateway", payment_id)
        raise HTTPException(status_code=502, detail="Payment gateway error")
    return {"refund_id": refund.get("id"), "status": payment.status.value}


# --------------------------------------------------------------------- escrow


@router.post("/escrow", response_model=dict, status_code=201)
async def create_escrow(
    req: CreateEscrowRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    await _payment_for(session, req.payment_id, current_actor, control=True)
    try:
        escrow = await PaymentManager(session).create_escrow(
            workflow_id=req.workflow_id,
            payment_id=req.payment_id,
            amount=req.amount,
            release_condition=req.release_condition,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": str(escrow.id), "status": escrow.status.value, "amount": escrow.amount}


@router.get("/escrow/{escrow_id}", response_model=dict)
async def get_escrow(
    escrow_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    escrow = await _escrow_for(session, escrow_id, current_actor)
    return {
        "id": str(escrow.id),
        "workflow_id": str(escrow.workflow_id) if escrow.workflow_id else None,
        "payment_id": str(escrow.payment_id) if escrow.payment_id else None,
        "amount": escrow.amount,
        "status": escrow.status.value,
        "release_condition": escrow.release_condition,
        "release_trigger": escrow.release_trigger,
        "released_at": escrow.released_at.isoformat() if escrow.released_at else None,
    }


@router.post("/escrow/{escrow_id}/release", response_model=dict)
async def release_escrow(
    escrow_id: UUID,
    release_trigger: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    escrow = await _escrow_for(session, escrow_id, current_actor, control=True)
    try:
        released = await PaymentManager(session).release_escrow(escrow.id, release_trigger)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": str(released.id),
        "status": released.status.value,
        "released_at": released.released_at.isoformat() if released.released_at else None,
    }


@router.post("/escrow/{escrow_id}/dispute", response_model=dict)
async def dispute_escrow(
    escrow_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    # Any participant, including the payee, may dispute held funds.
    escrow = await _escrow_for(session, escrow_id, current_actor)
    try:
        disputed = await PaymentManager(session).dispute_escrow(escrow.id, actor_id=current_actor.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": str(disputed.id), "status": disputed.status.value}


# ------------------------------------------------------------------- invoices


@router.post("/invoices", response_model=dict, status_code=201)
async def create_invoice(
    req: CreateInvoiceRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    payment = await _payment_for(session, req.payment_id, current_actor, control=True)
    if payment.workflow_id != req.workflow_id:
        raise HTTPException(status_code=400, detail="Payment does not belong to this workflow")
    try:
        invoice = await PaymentManager(session).create_invoice(
            workflow_id=req.workflow_id,
            payment_id=req.payment_id,
            amount=req.amount,
            description=req.description,
            tax_amount=req.tax_amount,
            payer_name=req.payer_name,
            payer_gst=req.payer_gst,
            payee_name=req.payee_name,
            payee_gst=req.payee_gst,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
    }


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    invoice = await session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")

    payment = await session.get(Payment, invoice.payment_id) if invoice.payment_id else None
    if payment is not None:
        access = await payment_access(session, payment)
    else:
        initiator = await workflow_initiator(session, invoice.workflow_id)
        ids = frozenset({initiator}) if initiator else frozenset()
        access = PaymentAccess(controllers=ids, viewers=ids)
    _enforce(access, current_actor, control=False, not_found="Invoice not found")

    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "amount": invoice.amount,
        "tax_amount": invoice.tax_amount,
        "total_amount": invoice.total_amount,
        "currency": invoice.currency,
        "description": invoice.description,
        "status": invoice.status,
        "payer_name": invoice.payer_name,
        "payee_name": invoice.payee_name,
    }


# -------------------------------------------------------------------- webhook


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """Handle Razorpay webhook events (payment.captured, payment.failed, ...).

    Deliberately outside session auth: the caller is Razorpay, not a user.
    The HMAC signature over the raw body is therefore the only thing
    authenticating this request, so it is verified before the payload is
    parsed or acted on.
    """
    raw_body = await request.body()

    if not RazorpayService.verify_webhook_signature(raw_body, x_razorpay_signature or ""):
        logger.warning(
            "Rejected Razorpay webhook with invalid or missing signature (%d bytes)",
            len(raw_body),
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    manager = PaymentManager(session)
    await manager.handle_webhook(data.get("event", ""), data.get("payload", {}))
    return {"status": "received"}
