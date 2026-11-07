"""delegate and escalate must check who is asking and what state it is in.

Both used to trust the request body: any logged-in user could name any
`from_actor` and any `to_actor`, which let them put themselves into an
approval's required approvers and then approve it. Rules pinned here:

* delegate: only the approver handing off their own slot, only while the
  approval is pending, and never to or from someone who already decided.
* escalate: only a current required approver, only while pending.
* both leave an audit entry.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.approval_engine import ApprovalEngine
from app.models.approval import Approval, ApprovalStatus, ApprovalStrategy
from app.models.audit_log import AuditLog


@pytest_asyncio.fixture
async def make_approval(db_session, sample_workflow):
    async def _make(required, *, approved=(), rejected=(), status=ApprovalStatus.PENDING):
        approval = Approval(
            id=uuid.uuid4(),
            workflow_id=sample_workflow.id,
            strategy=ApprovalStrategy.ALL,
            required_actors=[str(a) for a in required],
            approved_by=[str(a) for a in approved],
            rejected_by=[str(a) for a in rejected],
            status=status,
        )
        db_session.add(approval)
        await db_session.commit()
        await db_session.refresh(approval)
        return approval

    return _make


async def _audit_actions(db_session, approval_id):
    result = await db_session.execute(
        select(AuditLog.action).where(AuditLog.resource_id == str(approval_id))
    )
    return [row[0] for row in result.all()]


# ---------------------------------------------------------------- delegate


@pytest.mark.asyncio
async def test_delegate_by_a_third_party_is_refused(db_session, make_approval):
    victim, other, attacker = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([victim, other])

    with pytest.raises(PermissionError):
        await ApprovalEngine(db_session).delegate(
            approval.id, victim, attacker, acting_actor_id=attacker
        )

    await db_session.refresh(approval)
    assert set(approval.required_actors) == {str(victim), str(other)}


@pytest.mark.asyncio
async def test_delegate_by_the_approver_swaps_the_slot_and_is_audited(db_session, make_approval):
    me, other, delegate_to = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([me, other])

    await ApprovalEngine(db_session).delegate(approval.id, me, delegate_to, acting_actor_id=me)

    await db_session.refresh(approval)
    assert set(approval.required_actors) == {str(other), str(delegate_to)}
    assert "approval_delegated" in await _audit_actions(db_session, approval.id)


@pytest.mark.asyncio
async def test_delegate_requires_from_actor_to_be_a_required_approver(db_session, make_approval):
    required, outsider, target = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([required])

    with pytest.raises(ValueError, match="not a required approver"):
        await ApprovalEngine(db_session).delegate(
            approval.id, outsider, target, acting_actor_id=outsider
        )


@pytest.mark.asyncio
async def test_delegate_refused_once_from_actor_has_decided(db_session, make_approval):
    me, other, target = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([me, other], approved=[me])

    with pytest.raises(ValueError, match="already"):
        await ApprovalEngine(db_session).delegate(approval.id, me, target, acting_actor_id=me)


@pytest.mark.asyncio
async def test_delegate_refused_to_someone_who_already_decided(db_session, make_approval):
    me, decided = uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([me, decided], approved=[decided])

    with pytest.raises(ValueError, match="already"):
        await ApprovalEngine(db_session).delegate(approval.id, me, decided, acting_actor_id=me)


@pytest.mark.asyncio
async def test_delegate_refused_when_approval_is_not_pending(db_session, make_approval):
    me, target = uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([me], status=ApprovalStatus.APPROVED)

    with pytest.raises(ValueError, match="approved"):
        await ApprovalEngine(db_session).delegate(approval.id, me, target, acting_actor_id=me)


# ---------------------------------------------------------------- escalate


@pytest.mark.asyncio
async def test_escalate_by_a_non_approver_is_refused(db_session, make_approval):
    required, outsider = uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([required])

    with pytest.raises(PermissionError):
        await ApprovalEngine(db_session).escalate(
            approval.id, outsider, "x", acting_actor_id=outsider
        )

    await db_session.refresh(approval)
    assert approval.status == ApprovalStatus.PENDING
    assert approval.required_actors == [str(required)]


@pytest.mark.asyncio
async def test_escalate_by_a_required_approver_works_and_is_audited(db_session, make_approval):
    me, boss = uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([me])

    await ApprovalEngine(db_session).escalate(approval.id, boss, "need sign-off", acting_actor_id=me)

    await db_session.refresh(approval)
    assert approval.status == ApprovalStatus.ESCALATED
    assert approval.escalated_to == boss
    assert "approval_escalated" in await _audit_actions(db_session, approval.id)


@pytest.mark.asyncio
async def test_escalate_cannot_reopen_a_decided_approval(db_session, make_approval):
    me, boss = uuid.uuid4(), uuid.uuid4()
    approval = await make_approval([me], status=ApprovalStatus.APPROVED)

    with pytest.raises(ValueError, match="approved"):
        await ApprovalEngine(db_session).escalate(approval.id, boss, None, acting_actor_id=me)

    await db_session.refresh(approval)
    assert approval.status == ApprovalStatus.APPROVED


# --------------------------------------------------------------------- API


@pytest.mark.asyncio
async def test_api_delegate_names_someone_else_as_from_actor_is_403(
    client, auth_headers, current_actor, make_approval, db_session
):
    victim = uuid.uuid4()
    approval = await make_approval([victim])

    resp = await client.post(
        f"/approvals/{approval.id}/delegate",
        json={"from_actor": str(victim), "to_actor": str(current_actor.id)},
        headers=auth_headers,
    )

    assert resp.status_code == 403, resp.text
    await db_session.refresh(approval)
    assert approval.required_actors == [str(victim)]


@pytest.mark.asyncio
async def test_api_delegate_own_slot_is_allowed(
    client, auth_headers, current_actor, make_approval
):
    target = uuid.uuid4()
    approval = await make_approval([current_actor.id])

    resp = await client.post(
        f"/approvals/{approval.id}/delegate",
        json={"from_actor": str(current_actor.id), "to_actor": str(target)},
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["required_actors"] == [str(target)]


@pytest.mark.asyncio
async def test_api_escalate_by_non_approver_is_403(client, auth_headers, make_approval):
    approval = await make_approval([uuid.uuid4()])

    resp = await client.post(
        f"/approvals/{approval.id}/escalate",
        json={"escalated_to": str(uuid.uuid4())},
        headers=auth_headers,
    )

    assert resp.status_code == 403, resp.text
