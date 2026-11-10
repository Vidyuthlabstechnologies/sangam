from __future__ import annotations
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow, activity

with workflow.unsafe.imports_passed_through():
    from app.models.workflow import WorkflowPhase, WorkflowState
    from app.models.approval import ApprovalStrategy, ApprovalStatus


@activity.defn
async def log_workflow_event(workflow_id: str, event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "event": event,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }


@activity.defn
async def execute_phase(workflow_id: str, phase: str, context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "phase": phase,
        "status": "completed",
        "result": context,
        "timestamp": datetime.utcnow().isoformat(),
    }


@activity.defn
async def check_approvals(workflow_id: str, approval_config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "status": "pending",
        "required_actors": approval_config.get("required_actors", []),
        "timestamp": datetime.utcnow().isoformat(),
    }


@activity.defn
async def notify_actor(actor_id: str, message: str, channel: str = "in_app") -> Dict[str, Any]:
    return {
        "actor_id": actor_id,
        "message": message,
        "channel": channel,
        "status": "sent",
        "timestamp": datetime.utcnow().isoformat(),
    }


@activity.defn
async def detect_exceptions(workflow_id: str, phase_result: Dict[str, Any]) -> Dict[str, Any]:
    has_error = phase_result.get("status") == "error"
    has_timeout = phase_result.get("status") == "timeout"
    return {
        "workflow_id": workflow_id,
        "has_exception": has_error or has_timeout,
        "exceptions": [],
        "timestamp": datetime.utcnow().isoformat(),
    }


@activity.defn
async def execute_exception_subworkflow(
    workflow_id: str,
    exception_data: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "exception_id": str(uuid.uuid4()),
        "status": "routed",
        "assigned_to": exception_data.get("assigned_to"),
        "timestamp": datetime.utcnow().isoformat(),
    }


@activity.defn
async def settle_workflow(workflow_id: str, settlement_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "status": "settled",
        "amount": settlement_data.get("amount", 0),
        "timestamp": datetime.utcnow().isoformat(),
    }


@workflow.defn
class SangamWorkflow:
    @workflow.run
    async def run(self, workflow_input: Dict[str, Any]) -> Dict[str, Any]:
        workflow_id = workflow_input["workflow_id"]
        phases = workflow_input.get("phases", [p.value for p in WorkflowPhase])
        context = workflow_input.get("context", {})
        approval_config = workflow_input.get("approval_config", {})
        settlement_config = workflow_input.get("settlement_config", {})
        sla_timeout = workflow_input.get("sla_timeout_minutes", 60)

        await workflow.execute_activity(
            log_workflow_event,
            args=[workflow_id, "workflow_started", {"phases": phases}],
            start_to_close_timeout=timedelta(seconds=10),
        )

        for phase_name in phases:
            phase = WorkflowPhase(phase_name)

            await workflow.execute_activity(
                log_workflow_event,
                args=[workflow_id, f"phase_started:{phase.value}", {}],
                start_to_close_timeout=timedelta(seconds=10),
            )

            if phase == WorkflowPhase.APPROVAL and approval_config:
                approval_result = await workflow.execute_activity(
                    check_approvals,
                    args=[workflow_id, approval_config],
                    start_to_close_timeout=timedelta(hours=1),
                )

                for actor_id in approval_config.get("required_actors", []):
                    await workflow.execute_activity(
                        notify_actor,
                        args=[actor_id, f"Approval required for workflow {workflow_id}"],
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                context["approval"] = approval_result

            elif phase == WorkflowPhase.EXECUTION:
                phase_result = await workflow.execute_activity(
                    execute_phase,
                    args=[workflow_id, phase.value, context],
                    start_to_close_timeout=timedelta(hours=2),
                )
                context["execution_result"] = phase_result

                exception_check = await workflow.execute_activity(
                    detect_exceptions,
                    args=[workflow_id, phase_result],
                    start_to_close_timeout=timedelta(seconds=10),
                )

                if exception_check["has_exception"]:
                    await workflow.execute_activity(
                        execute_exception_subworkflow,
                        args=[workflow_id, {"source_phase": phase.value}],
                        start_to_close_timeout=timedelta(hours=1),
                    )

            elif phase == WorkflowPhase.VERIFICATION:
                phase_result = await workflow.execute_activity(
                    execute_phase,
                    args=[workflow_id, phase.value, context],
                    start_to_close_timeout=timedelta(hours=1),
                )
                context["verification"] = phase_result

            elif phase == WorkflowPhase.SETTLEMENT:
                if settlement_config:
                    settlement_result = await workflow.execute_activity(
                        settle_workflow,
                        args=[workflow_id, settlement_config],
                        start_to_close_timeout=timedelta(hours=1),
                    )
                    context["settlement"] = settlement_result
                else:
                    phase_result = await workflow.execute_activity(
                        execute_phase,
                        args=[workflow_id, phase.value, context],
                        start_to_close_timeout=timedelta(hours=1),
                    )
                    context["settlement"] = phase_result

            else:
                phase_result = await workflow.execute_activity(
                    execute_phase,
                    args=[workflow_id, phase.value, context],
                    start_to_close_timeout=timedelta(hours=1),
                )
                context[phase.value] = phase_result

            await workflow.execute_activity(
                log_workflow_event,
                args=[workflow_id, f"phase_completed:{phase.value}", context],
                start_to_close_timeout=timedelta(seconds=10),
            )

        await workflow.execute_activity(
            log_workflow_event,
            args=[workflow_id, "workflow_completed", context],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return {
            "workflow_id": workflow_id,
            "status": WorkflowState.COMPLETED.value,
            "context": context,
        }
