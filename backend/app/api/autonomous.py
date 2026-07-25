from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.api.dependencies import get_current_actor
from app.models.actor import Actor
from app.core.autonomous import auto_approve_low_risk, auto_retry_workflow, agent_auto_execute
from app.models.approval import Approval
from sqlalchemy import select

router = APIRouter(prefix="/autonomous", tags=["autonomous"])


class AutoRetryRequest(BaseModel):
    workflow_id: str
    max_retries: int = 3


@router.post("/retry")
async def trigger_auto_retry(
    request: AutoRetryRequest,
    current_actor: Actor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    success = await auto_retry_workflow(
        UUID(request.workflow_id), session, request.max_retries
    )
    return {"auto_retried": success}


@router.post("/execute/{workflow_id}")
async def trigger_auto_execute(
    workflow_id: str,
    current_actor: Actor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    success = await agent_auto_execute(UUID(workflow_id), session)
    return {"auto_executed": success}


@router.post("/auto-approve/{approval_id}")
async def trigger_auto_approve(
    approval_id: str,
    current_actor: Actor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Approval).where(Approval.id == UUID(approval_id))
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    success = await auto_approve_low_risk(approval, session)
    return {"auto_approved": success}
