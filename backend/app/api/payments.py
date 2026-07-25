from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_session
from app.models.actor import Actor
from app.models.payment import Payment, Escrow, Invoice, PaymentStatus, EscrowStatus
from app.core.payments import PaymentManager, RazorpayService
from app.api.dependencies import get_current_actor

router = APIRouter(prefix="/payments", tags=["payments"])


class InitiatePaymentRequest(BaseModel):
    workflow_id: UUID
    amount: float
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
    amount: float
    release_condition: Optional[str] = None


class CreateInvoiceRequest(BaseModel):
    workflow_id: UUID
    payment_id: UUID
    amount: float
    description: Optional[str] = None
    tax_amount: float = 0.0
    payer_name: Optional[str] = None
    payer_gst: Optional[str] = None
    payee_name: Optional[str] = None
    payee_gst: Optional[str] = None


@router.post("/initiate", response_model=dict, status_code=201)
async def initiate_payment(
    req: InitiatePaymentRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        manager = PaymentManager(session)
        result = await manager.initiate_payment(
            workflow_id=req.workflow_id,
            amount=req.amount,
            currency=req.currency,
            description=req.description,
            payer_actor_id=req.payer_actor_id,
            payee_actor_id=req.payee_actor_id,
            method=req.method,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify", response_model=dict)
async def verify_payment(
    req: VerifyPaymentRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        manager = PaymentManager(session)
        payment = await manager.verify_and_capture(
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature,
        )
        return {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "method": payment.method.value if payment.method else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{payment_id}", response_model=dict)
async def get_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
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
    amount: Optional[float] = Query(None),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment or not payment.razorpay_payment_id:
        raise HTTPException(status_code=404, detail="Payment not found or not captured")

    try:
        razorpay = RazorpayService()
        refund = await razorpay.refund_payment(payment.razorpay_payment_id, amount)
        payment.status = PaymentStatus.REFUNDED
        await session.commit()
        return {"refund_id": refund.get("id"), "status": "refunded"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/escrow", response_model=dict, status_code=201)
async def create_escrow(
    req: CreateEscrowRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        manager = PaymentManager(session)
        escrow = await manager.create_escrow(
            workflow_id=req.workflow_id,
            payment_id=req.payment_id,
            amount=req.amount,
            release_condition=req.release_condition,
        )
        return {
            "id": str(escrow.id),
            "status": escrow.status.value,
            "amount": escrow.amount,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/escrow/{escrow_id}/release", response_model=dict)
async def release_escrow(
    escrow_id: UUID,
    release_trigger: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        manager = PaymentManager(session)
        escrow = await manager.release_escrow(escrow_id, release_trigger)
        return {
            "id": str(escrow.id),
            "status": escrow.status.value,
            "released_at": escrow.released_at.isoformat() if escrow.released_at else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/escrow/{escrow_id}/dispute", response_model=dict)
async def dispute_escrow(
    escrow_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        manager = PaymentManager(session)
        escrow = await manager.dispute_escrow(escrow_id)
        return {"id": str(escrow.id), "status": escrow.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/invoices", response_model=dict, status_code=201)
async def create_invoice(
    req: CreateInvoiceRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        manager = PaymentManager(session)
        invoice = await manager.create_invoice(
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
        return {
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "total_amount": invoice.total_amount,
            "status": invoice.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    result = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
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


class WebhookRequest(BaseModel):
    event: str
    payload: dict


@router.post("/webhook")
async def razorpay_webhook(
    req: WebhookRequest,
    session: AsyncSession = Depends(get_session),
):
    """Handle Razorpay webhook events (payment.captured, payment.failed, etc.)"""
    # No auth required - webhook comes from Razorpay
    manager = PaymentManager(session)
    await manager.handle_webhook(req.event, req.payload)
    return {"status": "received"}
