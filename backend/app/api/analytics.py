from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.workflow import Workflow, WorkflowState
from app.models.actor import Actor
from app.models.approval import Approval, ApprovalStatus
from app.api.dependencies import get_current_actor
from app.core.access import workflow_visibility

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _visible_workflows(actor_id):
    return select(Workflow.id).where(workflow_visibility(actor_id))


@router.get("/summary")
async def analytics_summary(
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    visible = workflow_visibility(current_actor.id)
    total_wf = await session.scalar(select(func.count(Workflow.id)).where(visible))
    active_wf = await session.scalar(
        select(func.count(Workflow.id)).where(visible, Workflow.state == WorkflowState.ACTIVE)
    )
    completed_wf = await session.scalar(
        select(func.count(Workflow.id)).where(visible, Workflow.state == WorkflowState.COMPLETED)
    )
    paused_wf = await session.scalar(
        select(func.count(Workflow.id)).where(visible, Workflow.state == WorkflowState.PAUSED)
    )
    total_actors = await session.scalar(
        select(func.count(Actor.id)).where(
            (Actor.id == current_actor.id) | (Actor.created_by_id == current_actor.id)
        )
    )
    pending_approvals = await session.scalar(
        select(func.count(Approval.id)).where(
            Approval.status == ApprovalStatus.PENDING,
            Approval.workflow_id.in_(_visible_workflows(current_actor.id)),
        )
    )
    return {
        "total_workflows": total_wf or 0,
        "active_workflows": active_wf or 0,
        "completed_workflows": completed_wf or 0,
        "paused_workflows": paused_wf or 0,
        "total_actors": total_actors or 0,
        "pending_approvals": pending_approvals or 0,
    }


@router.get("/workflows-by-state")
async def workflows_by_state(
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    visible = workflow_visibility(current_actor.id)
    rows = await session.execute(
        select(Workflow.state, func.count(Workflow.id)).where(visible).group_by(Workflow.state)
    )
    return [{"state": s.value, "count": c} for s, c in rows]


@router.get("/approvals-over-time")
async def approvals_over_time(
    limit: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    from sqlalchemy import cast, Date
    visible = workflow_visibility(current_actor.id)
    rows = await session.execute(
        select(
            cast(Workflow.created_at, Date).label("date"),
            func.count(Workflow.id),
        )
        .where(visible)
        .group_by(cast(Workflow.created_at, Date))
        .order_by(cast(Workflow.created_at, Date).desc())
        .limit(limit)
    )
    return [{"date": str(d), "count": c} for d, c in rows]
