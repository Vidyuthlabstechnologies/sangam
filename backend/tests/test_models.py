import pytest
import uuid
from datetime import datetime

from app.models.workflow import Workflow, WorkflowPhase, WorkflowState, WaitingEvent
from app.models.actor import Actor, ActorType, Role, Permission
from app.models.approval import Approval, ApprovalStatus, ApprovalStrategy
from app.models.handoff import Handoff
from app.models.exception import ExceptionWorkflow, ExceptionTrigger, ExceptionSeverity


class TestWorkflowModel:
    def test_create_workflow(self):
        wf = Workflow(
            id=uuid.uuid4(),
            name="Test Procurement",
            description="Test workflow",
            initiator_id=uuid.uuid4(),
            current_phase=WorkflowPhase.INITIATION,
            state=WorkflowState.DRAFT,
            phases=[WorkflowPhase.INITIATION, WorkflowPhase.APPROVAL],
        )
        assert wf.name == "Test Procurement"
        assert wf.state == WorkflowState.DRAFT
        assert wf.current_phase == WorkflowPhase.INITIATION
        assert len(wf.phases) == 2

    def test_workflow_state_transitions(self):
        wf = Workflow(
            id=uuid.uuid4(),
            name="Test",
            initiator_id=uuid.uuid4(),
        )
        assert wf.state == WorkflowState.DRAFT
        wf.state = WorkflowState.ACTIVE
        assert wf.state == WorkflowState.ACTIVE
        wf.state = WorkflowState.PAUSED
        assert wf.state == WorkflowState.PAUSED
        wf.state = WorkflowState.COMPLETED
        assert wf.state == WorkflowState.COMPLETED

    def test_semantic_boundaries(self):
        wf = Workflow(
            id=uuid.uuid4(),
            name="Test",
            initiator_id=uuid.uuid4(),
            extra_attributes={"semantic_boundaries": [{"type": "data_privacy", "level": "high"}]},
        )
        boundaries = wf.semantic_boundaries
        assert len(boundaries) == 1
        assert boundaries[0]["type"] == "data_privacy"


class TestActorModel:
    def test_create_human_actor(self):
        actor = Actor(
            id=uuid.uuid4(),
            type=ActorType.HUMAN,
            name="John Doe",
            email="john@example.com",
            roles=[Role.INITIATOR, Role.APPROVER],
            permissions=[Permission.CREATE_WORKFLOW, Permission.APPROVE],
        )
        assert actor.type == ActorType.HUMAN
        assert actor.name == "John Doe"
        assert len(actor.roles) == 2

    def test_create_agent_actor(self):
        actor = Actor(
            id=uuid.uuid4(),
            type=ActorType.AGENT,
            name="ProcurementBot",
            extra_attributes={
                "capabilities": ["purchase_order", "invoice_validation"],
                "trust_score": 0.95,
            },
        )
        assert actor.type == ActorType.AGENT
        assert "purchase_order" in actor.capabilities
        assert actor.trust_score == 0.95

    def test_create_system_actor(self):
        actor = Actor(
            id=uuid.uuid4(),
            type=ActorType.SYSTEM,
            name="SAP ERP",
        )
        assert actor.type == ActorType.SYSTEM
        assert actor.is_active is True


class TestApprovalModel:
    def test_create_approval(self):
        approval = Approval(
            id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            strategy=ApprovalStrategy.ALL,
            required_actors=[uuid.uuid4(), uuid.uuid4()],
        )
        assert approval.status == ApprovalStatus.PENDING
        assert approval.strategy == ApprovalStrategy.ALL
        assert len(approval.required_actors) == 2

    def test_approval_strategies(self):
        any_approval = Approval(id=uuid.uuid4(), workflow_id=uuid.uuid4(), strategy=ApprovalStrategy.ANY)
        threshold = Approval(id=uuid.uuid4(), workflow_id=uuid.uuid4(), strategy=ApprovalStrategy.THRESHOLD, required_count=3)
        assert any_approval.strategy == ApprovalStrategy.ANY
        assert threshold.required_count == 3


class TestHandoffModel:
    def test_create_handoff(self):
        handoff = Handoff(
            id=uuid.uuid4(),
            workflow_id=uuid.uuid4(),
            from_actor_id=uuid.uuid4(),
            to_actor_id=uuid.uuid4(),
            artifact="Purchase Order #1234",
            notes="Please review and approve",
        )
        assert handoff.artifact == "Purchase Order #1234"
        assert handoff.verified is False


class TestExceptionModel:
    def test_create_exception(self):
        exc = ExceptionWorkflow(
            id=uuid.uuid4(),
            parent_workflow_id=uuid.uuid4(),
            trigger=ExceptionTrigger.TIMEOUT,
            severity=ExceptionSeverity.HIGH,
            message="Approval timed out after 24 hours",
        )
        assert exc.trigger == ExceptionTrigger.TIMEOUT
        assert exc.severity == ExceptionSeverity.HIGH
        assert exc.resolution is None
