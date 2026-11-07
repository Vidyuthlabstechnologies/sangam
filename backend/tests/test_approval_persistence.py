"""Approver lists must survive across requests.

`approved_by`, `rejected_by` and `required_actors` are plain JSON columns, which
SQLAlchemy cannot track mutations of. Appending in place silently drops the
change on flush, so who approved was never stored and any approval needing
more than one person stayed pending forever. Single-approver tests cannot see
this, because the status flips in memory and the status column is saved.

Every test here commits in one session and reads back from a fresh one, the way
two separate HTTP requests would.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.approval_engine import ApprovalEngine
from app.models.approval import Approval, ApprovalStatus, ApprovalStrategy


@pytest.fixture
def new_session(db_session):
    """Factory for a fresh session on the same engine: one per 'request'."""
    return async_sessionmaker(db_session.bind, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def make_approval(db_session, sample_workflow):
    async def _make(strategy, approvers, required_count=None):
        approval = Approval(
            id=uuid.uuid4(),
            workflow_id=sample_workflow.id,
            strategy=strategy,
            required_count=required_count,
            required_actors=[str(a) for a in approvers],
            approved_by=[],
            rejected_by=[],
            status=ApprovalStatus.PENDING,
        )
        db_session.add(approval)
        await db_session.commit()
        return approval.id

    return _make


async def _reload(new_session, approval_id):
    async with new_session() as s:
        return await s.get(Approval, approval_id)


async def _act(new_session, method, approval_id, actor):
    async with new_session() as s:
        return await getattr(ApprovalEngine(s), method)(approval_id, actor, "test")


@pytest.mark.asyncio
async def test_approver_is_recorded_after_approve(new_session, make_approval):
    a, b = uuid.uuid4(), uuid.uuid4()
    approval_id = await make_approval(ApprovalStrategy.ALL, [a, b])

    await _act(new_session, "approve", approval_id, a)

    row = await _reload(new_session, approval_id)
    assert row.approved_by == [str(a)]
    assert row.status == ApprovalStatus.PENDING


@pytest.mark.asyncio
async def test_all_strategy_completes_across_separate_requests(new_session, make_approval):
    a, b = uuid.uuid4(), uuid.uuid4()
    approval_id = await make_approval(ApprovalStrategy.ALL, [a, b])

    await _act(new_session, "approve", approval_id, a)
    await _act(new_session, "approve", approval_id, b)

    row = await _reload(new_session, approval_id)
    assert set(row.approved_by) == {str(a), str(b)}
    assert row.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_threshold_strategy_counts_approvals_across_requests(new_session, make_approval):
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval_id = await make_approval(ApprovalStrategy.THRESHOLD, [a, b, c], required_count=2)

    await _act(new_session, "approve", approval_id, a)
    assert (await _reload(new_session, approval_id)).status == ApprovalStatus.PENDING

    await _act(new_session, "approve", approval_id, b)
    assert (await _reload(new_session, approval_id)).status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_same_actor_cannot_approve_twice_across_requests(new_session, make_approval):
    a, b = uuid.uuid4(), uuid.uuid4()
    approval_id = await make_approval(ApprovalStrategy.ALL, [a, b])

    await _act(new_session, "approve", approval_id, a)

    with pytest.raises(ValueError, match="already approved"):
        await _act(new_session, "approve", approval_id, a)


@pytest.mark.asyncio
async def test_rejector_is_recorded_after_reject(new_session, make_approval):
    a, b = uuid.uuid4(), uuid.uuid4()
    approval_id = await make_approval(ApprovalStrategy.ALL, [a, b])

    await _act(new_session, "reject", approval_id, a)

    row = await _reload(new_session, approval_id)
    assert row.rejected_by == [str(a)]
    assert row.status == ApprovalStatus.REJECTED


@pytest.mark.asyncio
async def test_delegate_persists_required_actor_swap(new_session, make_approval):
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval_id = await make_approval(ApprovalStrategy.ALL, [a, b])

    async with new_session() as s:
        await ApprovalEngine(s).delegate(approval_id, a, c, acting_actor_id=a)

    row = await _reload(new_session, approval_id)
    assert set(row.required_actors) == {str(b), str(c)}
