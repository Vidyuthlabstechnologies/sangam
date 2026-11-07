"""No approval path may run attacker-influenced strings through eval().

The workflow-condition fix only reached coordinator.py. approval_engine.py and
autonomous.py still called eval(), where `().__class__.__bases__[0]
.__subclasses__()` walks out of the empty-builtins sandbox. Rejected or
malformed conditions must also fail CLOSED: create_approval auto-approves when
the condition evaluates false, so an evaluator that turns "error" into False
turned a broken condition into an approval.

Also pins that approval notifications reach the participants; a missing
`select` import was silently producing an empty recipient list.
"""
import uuid

import pytest

from app.core.approval_engine import ApprovalEngine, ConditionEvaluator
from app.core.autonomous import _evaluate_condition
from app.models.approval import ApprovalStatus, ApprovalStrategy

ESCAPE = "().__class__.__bases__[0].__subclasses__()"


def test_approval_evaluator_rejects_the_sandbox_escape():
    with pytest.raises(ValueError):
        ConditionEvaluator({}).evaluate(ESCAPE)


def test_approval_evaluator_still_evaluates_ordinary_conditions():
    assert ConditionEvaluator({"risk_score": 0.9}).evaluate("risk_score > 0.5") is True
    assert ConditionEvaluator({"risk_score": 0.1}).evaluate("risk_score > 0.5") is False


def test_template_variables_are_looked_up_not_pasted_into_source():
    assert ConditionEvaluator({"amount": 10}).evaluate("{{amount}} > 5") is True
    # A hostile VALUE is data: it can be compared, it cannot rewrite the expression.
    hostile = "x') or True or ('y"
    assert ConditionEvaluator({"amount": hostile}).evaluate("{{amount}} == 'x'") is False


def test_autonomous_evaluator_rejects_the_sandbox_escape():
    assert _evaluate_condition(ESCAPE, {}) is False


def test_autonomous_evaluator_still_evaluates_ordinary_conditions():
    assert _evaluate_condition("risk_score < 0.5", {"risk_score": 0.1}) is True
    assert _evaluate_condition("risk_score < 0.5", {"risk_score": 0.9}) is False


@pytest.mark.asyncio
async def test_unsafe_condition_leaves_approval_pending_not_auto_approved(
    db_session, sample_workflow
):
    approval = await ApprovalEngine(db_session).create_approval(
        workflow_id=sample_workflow.id,
        required_actors=[uuid.uuid4()],
        strategy=ApprovalStrategy.ALL,
        condition=ESCAPE,
        workflow_context={"risk_score": 0.1},
    )
    assert approval.status == ApprovalStatus.PENDING


@pytest.mark.asyncio
async def test_false_condition_still_auto_satisfies_as_before(db_session, sample_workflow):
    approval = await ApprovalEngine(db_session).create_approval(
        workflow_id=sample_workflow.id,
        required_actors=[uuid.uuid4()],
        condition="risk_score > 5",
        workflow_context={"risk_score": 1},
    )
    assert approval.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_approve_notifies_the_initiator_and_required_actors(
    client, auth_headers, current_actor, sample_workflow, db_session, monkeypatch
):
    from app.models.approval import Approval

    approval = Approval(
        id=uuid.uuid4(),
        workflow_id=sample_workflow.id,
        strategy=ApprovalStrategy.ANY,
        required_actors=[str(current_actor.id)],
        approved_by=[],
        rejected_by=[],
        status=ApprovalStatus.PENDING,
    )
    db_session.add(approval)
    await db_session.commit()

    captured = {}

    async def fake_notify(approval_id, workflow_id, status, actor_ids):
        captured["actor_ids"] = actor_ids

    monkeypatch.setattr("app.api.approvals.notify_approval_event", fake_notify)

    resp = await client.post(f"/approvals/{approval.id}/approve", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    assert str(sample_workflow.initiator_id) in captured["actor_ids"]
    assert str(current_actor.id) in captured["actor_ids"]
