"""Escrow that needs a manual API call to release is not escrow.

The product claim is "advance held, released automatically when delivery
is verified". release_escrow existed but had no caller, so every release
was manual. These tests pin the automatic path.
"""
import uuid

import pytest

from app.core.coordinator import Coordinator
from app.models.payment import Escrow, EscrowStatus, Payment, PaymentStatus


async def _held_escrow(db_session, workflow_id, condition="delivery_verified", amount=250000.0):
    payment = Payment(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        amount=amount,
        currency="INR",
        status=PaymentStatus.CAPTURED,
        razorpay_payment_id="pay_FIXTURE00001",
    )
    escrow = Escrow(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        payment_id=payment.id,
        amount=amount,
        status=EscrowStatus.HELD,
        release_condition=condition,
    )
    db_session.add_all([payment, escrow])
    await db_session.commit()
    await db_session.refresh(escrow)
    return escrow


@pytest.mark.asyncio
async def test_handoff_verification_releases_escrow(db_session, sample_workflow, sample_actors):
    escrow = await _held_escrow(db_session, sample_workflow.id)
    coord = Coordinator(db_session)

    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id,
        to_actor_id=sample_actors[1].id,
        artifact="COA-4471.pdf",
        artifact_type="coa",
    )
    await coord.verify_handoff(handoff.id, actor_id=sample_actors[1].id)

    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.RELEASED
    assert escrow.released_at is not None
    assert str(handoff.id) in (escrow.release_trigger or "")


@pytest.mark.asyncio
async def test_unmet_condition_leaves_escrow_held(db_session, sample_workflow, sample_actors):
    """A condition referencing absent context must not release funds."""
    escrow = await _held_escrow(db_session, sample_workflow.id, condition="lab_certified")
    coord = Coordinator(db_session)

    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id,
        to_actor_id=sample_actors[1].id,
        artifact="partial-delivery.pdf",
    )
    await coord.verify_handoff(handoff.id, actor_id=sample_actors[1].id)

    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.HELD


@pytest.mark.asyncio
async def test_already_released_escrow_untouched(db_session, sample_workflow, sample_actors):
    escrow = await _held_escrow(db_session, sample_workflow.id)
    escrow.status = EscrowStatus.RELEASED
    await db_session.commit()

    coord = Coordinator(db_session)
    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id,
        to_actor_id=sample_actors[1].id,
    )
    await coord.verify_handoff(handoff.id, actor_id=sample_actors[1].id)

    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.RELEASED


@pytest.mark.asyncio
async def test_gateway_failure_does_not_break_handoff(
    db_session, sample_workflow, sample_actors, monkeypatch
):
    """A payment-gateway outage must not fail the handoff itself.

    The goods physically arrived; recording that fact cannot depend on
    Razorpay being reachable.
    """
    escrow = await _held_escrow(db_session, sample_workflow.id)
    coord = Coordinator(db_session)

    from app.core.payments import PaymentManager

    async def boom(*args, **kwargs):
        raise RuntimeError("Razorpay unreachable")

    monkeypatch.setattr(PaymentManager, "release_escrow", boom)

    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id,
        to_actor_id=sample_actors[1].id,
        artifact="COA-4471.pdf",
    )
    verified = await coord.verify_handoff(handoff.id, actor_id=sample_actors[1].id)

    assert verified.verified is True, "Handoff must succeed despite gateway failure"
    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.HELD, "Funds stay held for retry"


@pytest.mark.asyncio
async def test_no_escrow_is_a_no_op(db_session, sample_workflow, sample_actors):
    coord = Coordinator(db_session)
    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id,
        to_actor_id=sample_actors[1].id,
    )
    verified = await coord.verify_handoff(handoff.id, actor_id=sample_actors[1].id)
    assert verified.verified is True
