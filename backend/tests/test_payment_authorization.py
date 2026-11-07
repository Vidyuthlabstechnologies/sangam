"""Payments, escrow and refunds must check who is asking and what state it is in.

Every payment endpoint used to require only "logged in": any user could read,
release, dispute or refund any other party's money. And release_escrow marked
the escrow released before the gateway call, so a gateway failure left a dirty
RELEASED status that the next commit on the session would persist.

Roles: the payer and the workflow initiator CONTROL a payment (release,
refund, create escrow/invoice). The payee can also VIEW and DISPUTE. Anyone
else gets 404, so a payment's existence is not revealed to strangers.
"""
import uuid

import pytest
import pytest_asyncio

from app.core.coordinator import Coordinator
from app.core.payments import PaymentManager, RazorpayService
from app.models.payment import Escrow, EscrowStatus, Payment, PaymentStatus


@pytest_asyncio.fixture
async def make_money(db_session):
    async def _make(
        workflow,
        *,
        payer=None,
        payee=None,
        status=PaymentStatus.CAPTURED,
        escrow_status=EscrowStatus.HELD,
        amount=1000.0,
    ):
        payment = Payment(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            amount=amount,
            currency="INR",
            status=status,
            razorpay_payment_id="pay_FIXTURE00001" if status == PaymentStatus.CAPTURED else None,
            payer_actor_id=payer,
            payee_actor_id=payee,
        )
        db_session.add(payment)
        await db_session.commit()
        escrow = Escrow(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            payment_id=payment.id,
            amount=amount,
            status=escrow_status,
            release_condition="delivery_verified",
        )
        db_session.add(escrow)
        await db_session.commit()
        return payment, escrow

    return _make


@pytest_asyncio.fixture
async def as_role(current_actor, owned_workflow, sample_workflow, make_money):
    """Build money where the authenticated caller holds exactly one role."""

    async def _build(role, **kwargs):
        other = uuid.uuid4()
        if role == "initiator":
            return await make_money(owned_workflow, payer=other, payee=other, **kwargs)
        if role == "payer":
            return await make_money(sample_workflow, payer=current_actor.id, payee=other, **kwargs)
        if role == "payee":
            return await make_money(sample_workflow, payer=other, payee=current_actor.id, **kwargs)
        return await make_money(sample_workflow, payer=other, payee=uuid.uuid4(), **kwargs)

    return _build


# --------------------------------------------------------------------- reads


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["initiator", "payer", "payee"])
async def test_participants_can_read_payment_and_escrow(client, auth_headers, as_role, role):
    payment, escrow = await as_role(role)

    assert (await client.get(f"/payments/{payment.id}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"/payments/escrow/{escrow.id}", headers=auth_headers)).status_code == 200


@pytest.mark.asyncio
async def test_strangers_get_404_not_403(client, auth_headers, as_role):
    payment, escrow = await as_role("stranger")

    assert (await client.get(f"/payments/{payment.id}", headers=auth_headers)).status_code == 404
    assert (await client.get(f"/payments/escrow/{escrow.id}", headers=auth_headers)).status_code == 404


# ------------------------------------------------------------------- release


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["payer", "initiator"])
async def test_controllers_can_release(client, auth_headers, as_role, role):
    _, escrow = await as_role(role)

    resp = await client.post(f"/payments/escrow/{escrow.id}/release", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "released"


@pytest.mark.asyncio
async def test_payee_cannot_release_their_own_payout(client, auth_headers, as_role, db_session):
    _, escrow = await as_role("payee")

    resp = await client.post(f"/payments/escrow/{escrow.id}/release", headers=auth_headers)

    assert resp.status_code == 403, resp.text
    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.HELD


@pytest.mark.asyncio
async def test_stranger_cannot_release(client, auth_headers, as_role, db_session):
    _, escrow = await as_role("stranger")

    resp = await client.post(f"/payments/escrow/{escrow.id}/release", headers=auth_headers)

    assert resp.status_code == 404
    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.HELD


@pytest.mark.asyncio
async def test_release_twice_is_refused(client, auth_headers, as_role):
    _, escrow = await as_role("payer")
    first = await client.post(f"/payments/escrow/{escrow.id}/release", headers=auth_headers)
    second = await client.post(f"/payments/escrow/{escrow.id}/release", headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 400
    assert "released" in second.json()["detail"]


@pytest.mark.asyncio
async def test_disputed_escrow_cannot_be_released(client, auth_headers, as_role):
    _, escrow = await as_role("payer", escrow_status=EscrowStatus.DISPUTED)

    resp = await client.post(f"/payments/escrow/{escrow.id}/release", headers=auth_headers)

    assert resp.status_code == 400
    assert "disputed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_failed_capture_leaves_escrow_held_even_after_a_later_commit(
    db_session, sample_workflow, make_money, monkeypatch
):
    payment, escrow = await make_money(sample_workflow)

    async def gateway_down(self, *args, **kwargs):
        raise RuntimeError("gateway unreachable")

    monkeypatch.setattr(RazorpayService, "capture_payment", gateway_down)

    with pytest.raises(ValueError):
        await PaymentManager(db_session).release_escrow(escrow.id, "test")

    await db_session.commit()  # any later commit on the same session
    await db_session.refresh(escrow)
    assert escrow.status == EscrowStatus.HELD
    assert escrow.released_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state", [EscrowStatus.RELEASED, EscrowStatus.DISPUTED, EscrowStatus.REFUNDED]
)
async def test_only_held_escrow_can_be_released(db_session, sample_workflow, make_money, state):
    _, escrow = await make_money(sample_workflow, escrow_status=state)

    with pytest.raises(ValueError, match=state.value):
        await PaymentManager(db_session).release_escrow(escrow.id, "test")


# ------------------------------------------------------------------- dispute


@pytest.mark.asyncio
async def test_payee_can_dispute(client, auth_headers, as_role):
    _, escrow = await as_role("payee")

    resp = await client.post(f"/payments/escrow/{escrow.id}/dispute", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "disputed"


@pytest.mark.asyncio
async def test_stranger_cannot_dispute(client, auth_headers, as_role):
    _, escrow = await as_role("stranger")
    resp = await client.post(f"/payments/escrow/{escrow.id}/dispute", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_released_escrow_cannot_be_disputed(client, auth_headers, as_role):
    _, escrow = await as_role("payer", escrow_status=EscrowStatus.RELEASED)
    resp = await client.post(f"/payments/escrow/{escrow.id}/dispute", headers=auth_headers)
    assert resp.status_code == 400


# -------------------------------------------------------------------- refund


@pytest.mark.asyncio
async def test_payer_can_refund_in_full(client, auth_headers, as_role, db_session):
    payment, _ = await as_role("payer")

    resp = await client.post(f"/payments/{payment.id}/refund", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.REFUNDED


@pytest.mark.asyncio
async def test_partial_refund_is_recorded_as_partial(client, auth_headers, as_role, db_session):
    payment, _ = await as_role("payer", amount=1000.0)

    resp = await client.post(
        f"/payments/{payment.id}/refund", params={"amount": 250}, headers=auth_headers
    )

    assert resp.status_code == 200, resp.text
    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.PARTIALLY_REFUNDED


@pytest.mark.asyncio
async def test_refund_cannot_exceed_the_payment(client, auth_headers, as_role):
    payment, _ = await as_role("payer", amount=1000.0)
    resp = await client.post(
        f"/payments/{payment.id}/refund", params={"amount": 1000.01}, headers=auth_headers
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_payee_cannot_refund(client, auth_headers, as_role):
    payment, _ = await as_role("payee")
    resp = await client.post(f"/payments/{payment.id}/refund", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stranger_cannot_refund(client, auth_headers, as_role):
    payment, _ = await as_role("stranger")
    resp = await client.post(f"/payments/{payment.id}/refund", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_uncaptured_payment_cannot_be_refunded(client, auth_headers, as_role):
    payment, _ = await as_role("payer", status=PaymentStatus.PENDING)
    resp = await client.post(f"/payments/{payment.id}/refund", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refund_error_does_not_leak_gateway_internals(
    client, auth_headers, as_role, monkeypatch
):
    payment, _ = await as_role("payer")

    async def boom(self, *args, **kwargs):
        raise RuntimeError("secret-gateway-internal-detail")

    monkeypatch.setattr(RazorpayService, "refund_payment", boom)
    resp = await client.post(f"/payments/{payment.id}/refund", headers=auth_headers)

    assert resp.status_code == 502
    assert "secret-gateway-internal-detail" not in resp.text


# ------------------------------------------------------- initiate and escrow


@pytest.mark.asyncio
async def test_cannot_initiate_payment_on_someone_elses_workflow(
    client, auth_headers, sample_workflow
):
    resp = await client.post(
        "/payments/initiate",
        json={"workflow_id": str(sample_workflow.id), "amount": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_initiate_on_unknown_workflow_is_404(client, auth_headers):
    resp = await client.post(
        "/payments/initiate",
        json={"workflow_id": str(uuid.uuid4()), "amount": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payee_cannot_create_escrow_on_a_payment(client, auth_headers, as_role):
    payment, _ = await as_role("payee")
    resp = await client.post(
        "/payments/escrow",
        json={"workflow_id": str(payment.workflow_id), "payment_id": str(payment.id), "amount": 10},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_escrow_cannot_exceed_its_payment(client, auth_headers, as_role):
    payment, _ = await as_role("payer", amount=1000.0)
    resp = await client.post(
        "/payments/escrow",
        json={"workflow_id": str(payment.workflow_id), "payment_id": str(payment.id), "amount": 1000.01},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ------------------------------------------------------------------ handoffs


@pytest.mark.asyncio
async def test_only_the_receiver_can_verify_a_handoff(
    db_session, sample_workflow, sample_actors, make_money
):
    """Verifying a handoff auto-releases escrow, so it is a money action."""
    _, escrow = await make_money(sample_workflow)
    coord = Coordinator(db_session)
    handoff = await coord.create_handoff(
        workflow_id=sample_workflow.id,
        from_actor_id=sample_actors[0].id,
        to_actor_id=sample_actors[1].id,
        artifact="COA-1.pdf",
        artifact_type="coa",
    )

    with pytest.raises(PermissionError):
        await coord.verify_handoff(handoff.id, actor_id=sample_actors[0].id)

    await db_session.refresh(handoff)
    await db_session.refresh(escrow)
    assert handoff.verified is False
    assert escrow.status == EscrowStatus.HELD
