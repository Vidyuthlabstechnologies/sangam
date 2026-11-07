"""Who may see, and who may move, a payment's money.

The payer and the initiator of the payment's workflow CONTROL it: they can
release escrow, refund, and create escrow or invoices against it. The payee
can additionally VIEW it and DISPUTE. Anyone else is a stranger, and callers
should answer 404 rather than 403 so the existence of a payment is not
revealed to them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.workflow import Workflow

__all__ = ["PaymentAccess", "payment_access", "workflow_initiator"]


@dataclass(frozen=True)
class PaymentAccess:
    controllers: frozenset[UUID]
    viewers: frozenset[UUID]

    def can_control(self, actor_id: UUID) -> bool:
        return actor_id in self.controllers

    def can_view(self, actor_id: UUID) -> bool:
        return actor_id in self.viewers


async def workflow_initiator(session: AsyncSession, workflow_id: Optional[UUID]) -> Optional[UUID]:
    if workflow_id is None:
        return None
    result = await session.execute(
        select(Workflow.initiator_id).where(Workflow.id == workflow_id)
    )
    return result.scalar_one_or_none()


async def payment_access(session: AsyncSession, payment: Payment) -> PaymentAccess:
    initiator = await workflow_initiator(session, payment.workflow_id)
    controllers = frozenset(a for a in (payment.payer_actor_id, initiator) if a is not None)
    viewers = controllers | frozenset(a for a in (payment.payee_actor_id,) if a is not None)
    return PaymentAccess(controllers=controllers, viewers=viewers)
