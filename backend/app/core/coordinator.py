from __future__ import annotations
import uuid
import asyncio
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Callable, Awaitable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.workflow import Workflow, WorkflowPhase, WorkflowState
from app.models.actor import Actor, ActorType
from app.models.handoff import Handoff
from app.models.approval import Approval, ApprovalStrategy, ApprovalStatus
from app.models.exception import ExceptionWorkflow, ExceptionTrigger, ExceptionSeverity
from app.core.approval_engine import ApprovalEngine
from app.core.audit import AuditService


class ExecutionPattern(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    RACE = "race"


class Coordinator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.approval_engine = ApprovalEngine(session)
        self.audit = AuditService(session)

    async def transition_phase(
        self,
        workflow: Workflow,
        to_phase: WorkflowPhase,
        actor_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> Workflow:
        if workflow.state in (WorkflowState.COMPLETED, WorkflowState.FAILED):
            raise ValueError(f"Cannot transition workflow in state: {workflow.state}")

        from_phase = workflow.current_phase
        workflow.current_phase = to_phase

        if to_phase == WorkflowPhase.EXECUTION and workflow.state == WorkflowState.DRAFT:
            workflow.state = WorkflowState.ACTIVE

        await self.session.commit()
        await self.session.refresh(workflow)

        await self.audit.log(
            action="phase_transition",
            resource_type="workflow",
            resource_id=str(workflow.id),
            actor_id=actor_id,
            workflow_id=workflow.id,
            details={
                "from_phase": from_phase.value,
                "to_phase": to_phase.value,
                "reason": reason,
            },
        )

        return workflow

    async def create_handoff(
        self,
        workflow_id: UUID,
        from_actor_id: UUID,
        to_actor_id: UUID,
        artifact: Optional[str] = None,
        artifact_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Handoff:
        handoff = Handoff(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            from_actor_id=from_actor_id,
            to_actor_id=to_actor_id,
            artifact=artifact,
            artifact_type=artifact_type,
            notes=notes,
            timestamp=datetime.utcnow(),
        )
        self.session.add(handoff)
        await self.session.commit()
        await self.session.refresh(handoff)

        await self.audit.log(
            action="handoff_created",
            resource_type="handoff",
            resource_id=str(handoff.id),
            workflow_id=workflow_id,
            details={
                "from_actor": str(from_actor_id),
                "to_actor": str(to_actor_id),
                "artifact": artifact,
            },
        )

        return handoff

    async def verify_handoff(
        self,
        handoff_id: UUID,
        actor_id: UUID,
    ) -> Handoff:
        result = await self.session.execute(
            select(Handoff).where(Handoff.id == handoff_id)
        )
        handoff = result.scalar_one_or_none()
        if not handoff:
            raise ValueError("Handoff not found")

        handoff.verified = True
        handoff.verified_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(handoff)
        return handoff

    async def execute_parallel(
        self,
        workflow_id: UUID,
        phases: List[WorkflowPhase],
    ) -> Dict[str, Any]:
        completed = {}
        exceptions = []

        for phase in phases:
            try:
                completed[phase.value] = {"status": "completed"}
            except Exception as e:
                exceptions.append({"phase": phase.value, "error": str(e)})
                await self._handle_exception(
                    workflow_id=workflow_id,
                    trigger=ExceptionTrigger.ERROR,
                    message=f"Phase {phase.value} failed: {e}",
                    assigned_to=None,
                )

        return {"completed": completed, "exceptions": exceptions}

    async def execute_conditional(
        self,
        workflow_id: UUID,
        condition: str,
        if_phase: WorkflowPhase,
        else_phase: Optional[WorkflowPhase] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowPhase:
        evaluator = ConditionEvaluator(context or {})
        if evaluator.evaluate(condition):
            return if_phase
        return else_phase or if_phase

    async def create_waiting_event(
        self,
        workflow_id: UUID,
        actor_id: UUID,
        event_type: str,
        reason: Optional[str] = None,
        sla_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        from app.models.workflow import WaitingEvent

        event = WaitingEvent(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            actor_id=actor_id,
            event_type=event_type,
            reason=reason,
            sla_deadline=(
                datetime.utcnow() + __import__("datetime").timedelta(minutes=sla_minutes)
                if sla_minutes else None
            ),
        )
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)

        await self.audit.log(
            action="waiting_event_created",
            resource_type="waiting_event",
            resource_id=str(event.id),
            workflow_id=workflow_id,
            details={
                "event_type": event_type,
                "actor_id": str(actor_id),
                "sla_minutes": sla_minutes,
            },
        )

        return {
            "id": str(event.id),
            "workflow_id": str(event.workflow_id),
            "event_type": event.event_type,
            "reason": event.reason,
            "sla_deadline": event.sla_deadline.isoformat() if event.sla_deadline else None,
        }

    async def resolve_waiting_event(self, event_id: UUID) -> None:
        from app.models.workflow import WaitingEvent

        result = await self.session.execute(
            select(WaitingEvent).where(WaitingEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.resolved_at = datetime.utcnow()
            await self.session.commit()

    async def _handle_exception(
        self,
        workflow_id: UUID,
        trigger: ExceptionTrigger,
        message: str,
        assigned_to: Optional[UUID] = None,
        severity: ExceptionSeverity = ExceptionSeverity.MEDIUM,
    ) -> ExceptionWorkflow:
        exc = ExceptionWorkflow(
            id=uuid.uuid4(),
            parent_workflow_id=workflow_id,
            trigger=trigger,
            severity=severity,
            message=message,
            assigned_to=assigned_to,
        )
        self.session.add(exc)
        await self.session.commit()
        await self.session.refresh(exc)

        await self.audit.log(
            action="exception_created",
            resource_type="exception",
            resource_id=str(exc.id),
            workflow_id=workflow_id,
            details={
                "trigger": trigger.value,
                "severity": severity.value,
                "message": message,
            },
        )

        return exc


class ConditionEvaluator:
    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def evaluate(self, condition: str) -> bool:
        if not condition:
            return True
        try:
            return bool(eval(condition, {"__builtins__": {}}, self.context))
        except Exception:
            return False
