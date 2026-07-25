from __future__ import annotations
import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.workflow import Workflow, WorkflowState
from app.models.approval import Approval, ApprovalStatus, ApprovalStrategy
from app.models.actor import Actor, ActorType
from app.core.sarvam import SarvamAI
from app.core.audit import AuditService
from app.core.notifications import notify_workflow_event

logger = logging.getLogger("sangam.autonomous")


async def auto_approve_low_risk(
    approval: Approval,
    session: AsyncSession,
) -> bool:
    if approval.strategy != ApprovalStrategy.ANY:
        return False
    if not approval.condition:
        return False

    result = await session.execute(
        select(Workflow).where(Workflow.id == approval.workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        return False

    risk_score = (workflow.extra_attributes or {}).get(
        "semantic_boundaries", {}
    ).get("risk_score", 1.0)

    if risk_score > 0.3:
        return False

    try:
        auto_approver_result = await session.execute(
            select(Actor).where(
                Actor.type == ActorType.AGENT,
                Actor.is_active == True,
            )
        )
        auto_approver = auto_approver_result.scalar_one_or_none()
        if not auto_approver:
            return False

        ctx = {
            "workflow_name": workflow.name,
            "workflow_description": workflow.description or "",
            "risk_score": risk_score,
        }

        condition_result = _evaluate_condition(approval.condition, ctx)
        if not condition_result:
            return False

        approvers = approval.approved_by or []
        if str(auto_approver.id) not in approvers:
            approvers.append(str(auto_approver.id))
        approval.approved_by = approvers

        required = approval.required_actors or []
        if str(auto_approver.id) not in required:
            required.append(str(auto_approver.id))
        approval.required_actors = required

        if approval.strategy == ApprovalStrategy.ANY:
            approval.status = ApprovalStatus.APPROVED
        elif approval.strategy == ApprovalStrategy.ALL:
            if set(approvers) == set(required):
                approval.status = ApprovalStatus.APPROVED
        elif approval.strategy == ApprovalStrategy.THRESHOLD:
            threshold = approval.required_count or len(required)
            if len(approvers) >= threshold:
                approval.status = ApprovalStatus.APPROVED

        await session.commit()

        audit = AuditService(session)
        await audit.log(
            action="auto_approved",
            resource_type="approval",
            resource_id=str(approval.id),
            workflow_id=str(workflow.id),
            details={"risk_score": risk_score, "condition": approval.condition},
        )

        try:
            await notify_workflow_event(
                session,
                [str(workflow.initiator_id)],
                "approval_needed",
                workflow.name,
                str(workflow.id),
            )
        except Exception:
            pass

        logger.info("Auto-approved approval %s for workflow %s", approval.id, workflow.name)
        return True
    except Exception as e:
        logger.error("Auto-approve failed: %s", e)
        return False


async def auto_retry_workflow(
    workflow_id: UUID,
    session: AsyncSession,
    max_retries: int = 3,
) -> bool:
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        return False

    retry_count = (workflow.extra_attributes or {}).get("auto_retry_count", 0)
    if retry_count >= max_retries:
        logger.warning("Workflow %s exceeded max auto-retries (%s)", workflow_id, max_retries)
        return False

    if workflow.state not in (WorkflowState.FAILED,):
        return False

    attrs = dict(workflow.extra_attributes or {})
    attrs["auto_retry_count"] = retry_count + 1
    workflow.extra_attributes = attrs
    workflow.state = WorkflowState.ACTIVE
    await session.commit()

    audit = AuditService(session)
    await audit.log(
        action="auto_retried",
        resource_type="workflow",
        resource_id=str(workflow.id),
        details={"retry_count": retry_count + 1},
    )

    logger.info("Auto-retried workflow %s (attempt %s)", workflow_id, retry_count + 1)
    return True


async def agent_auto_execute(
    workflow_id: UUID,
    session: AsyncSession,
) -> bool:
    result = await session.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        return False

    result = await session.execute(
        select(Actor).where(
            Actor.type == ActorType.AGENT,
            Actor.is_active == True,
        )
    )
    agents = result.scalars().all()
    if not agents:
        return False

    if workflow.state != WorkflowState.ACTIVE:
        return False

    try:
        agent = agents[0]
        sarvam = SarvamAI()
        llm_result = await sarvam.llm_complete(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an autonomous workflow executor. "
                        "Given a workflow name, description, and current phase, "
                        "determine what action to take. "
                        "Respond with one of: "
                        "{\"action\": \"transition\", \"next_phase\": \"...\"} | "
                        "{\"action\": \"complete\"} | "
                        "{\"action\": \"request_info\", \"question\": \"...\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Workflow: {workflow.name}\n"
                        f"Description: {workflow.description or ''}\n"
                        f"Current phase: {workflow.current_phase}\n"
                        f"Remaining phases: {[p for p in (workflow.phases or []) if p != workflow.current_phase]}\n"
                    ),
                },
            ],
            model="sarvam-30b",
            temperature=0.1,
        )

        import json, re
        json_match = re.search(r'\{.*\}', llm_result.content, re.DOTALL)
        if not json_match:
            return False

        decision = json.loads(json_match.group())
        action = decision.get("action")

        if action == "transition":
            next_phase = decision.get("next_phase")
            if next_phase and next_phase in (workflow.phases or []):
                from app.core.coordinator import Coordinator
                coord = Coordinator(session)
                await coord.transition_phase(workflow, next_phase, str(agent.id))
                logger.info("Agent auto-transitioned %s to %s", workflow_id, next_phase)
                return True

        elif action == "complete":
            workflow.state = WorkflowState.COMPLETED
            await session.commit()
            audit = AuditService(session)
            await audit.log(
                action="auto_completed",
                resource_type="workflow",
                resource_id=str(workflow.id),
                details={"agent_id": str(agent.id)},
            )
            logger.info("Agent auto-completed workflow %s", workflow_id)
            return True

        return False
    except Exception as e:
        logger.error("Agent auto-execute failed for %s: %s", workflow_id, e)
        return False


def _evaluate_condition(condition: str, context: dict) -> bool:
    try:
        safe_globals = {"__builtins__": {}}
        safe_locals = context.copy()
        result = eval(condition, safe_globals, safe_locals)
        return bool(result)
    except Exception as e:
        logger.warning("Condition eval failed: %s", e)
        return False
