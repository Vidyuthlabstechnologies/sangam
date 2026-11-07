import logging
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.streaming import notify_approval_event
from app.models.workflow import Workflow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.actor import Actor
from app.models.approval import Approval, ApprovalStrategy
from app.core.approval_engine import ApprovalEngine
from app.core.autonomous import auto_approve_low_risk
from app.api.dependencies import get_current_actor
from pydantic import BaseModel

router = APIRouter(prefix="/approvals", tags=["approvals"])

logger = logging.getLogger("sangam.approvals")


class CreateApprovalRequest(BaseModel):
    workflow_id: UUID
    required_actors: List[UUID]
    strategy: ApprovalStrategy = ApprovalStrategy.ALL
    required_count: Optional[int] = None
    condition: Optional[str] = None
    expires_in_minutes: Optional[int] = None


class ApprovalResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    strategy: str
    required_actors: List[UUID]
    approved_by: List[UUID]
    rejected_by: List[UUID]
    status: str
    condition: Optional[str] = None
    expires_at: Optional[str] = None
    escalated_to: Optional[UUID] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class DelegateRequest(BaseModel):
    from_actor: UUID
    to_actor: UUID


class EscalateRequest(BaseModel):
    escalated_to: UUID
    reason: Optional[str] = None


@router.post("/", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
async def create_approval(
    req: CreateApprovalRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    engine = ApprovalEngine(session)
    approval = await engine.create_approval(
        workflow_id=req.workflow_id,
        required_actors=req.required_actors,
        strategy=req.strategy,
        required_count=req.required_count,
        condition=req.condition,
        expires_in_minutes=req.expires_in_minutes,
    )
    try:
        await auto_approve_low_risk(approval, session)
    except Exception:
        logger.exception("Auto-approval check failed for approval %s", approval.id)
    return approval


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        result = await session.get(Approval, approval_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Approval not found")
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found")
    return result


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: UUID,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    engine = ApprovalEngine(session)
    try:
        approval = await engine.approve(approval_id, current_actor.id, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        wf_result = await session.execute(
            select(Workflow).where(Workflow.id == approval.workflow_id)
        )
        workflow = wf_result.scalar_one()
        actor_ids = [str(workflow.initiator_id)] + [str(a) for a in (approval.required_actors or [])]
    except Exception:
        # Do not swallow silently: a missing import here once made every
        # notification go to an empty recipient list with no trace.
        logger.exception("Could not resolve recipients for approval %s", approval_id)
        actor_ids = []
    await notify_approval_event(str(approval_id), str(approval.workflow_id), approval.status.value, actor_ids)
    return approval


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: UUID,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    engine = ApprovalEngine(session)
    try:
        approval = await engine.reject(approval_id, current_actor.id, reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        wf_result = await session.execute(
            select(Workflow).where(Workflow.id == approval.workflow_id)
        )
        workflow = wf_result.scalar_one()
        actor_ids = [str(workflow.initiator_id)] + [str(a) for a in (approval.required_actors or [])]
    except Exception:
        # Do not swallow silently: a missing import here once made every
        # notification go to an empty recipient list with no trace.
        logger.exception("Could not resolve recipients for approval %s", approval_id)
        actor_ids = []
    await notify_approval_event(str(approval_id), str(approval.workflow_id), approval.status.value, actor_ids)
    return approval


@router.post("/{approval_id}/escalate", response_model=ApprovalResponse)
async def escalate(
    approval_id: UUID,
    req: EscalateRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    engine = ApprovalEngine(session)
    try:
        approval = await engine.escalate(
            approval_id, req.escalated_to, req.reason, acting_actor_id=current_actor.id
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return approval


@router.post("/{approval_id}/delegate", response_model=ApprovalResponse)
async def delegate(
    approval_id: UUID,
    req: DelegateRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    engine = ApprovalEngine(session)
    try:
        approval = await engine.delegate(
            approval_id, req.from_actor, req.to_actor, acting_actor_id=current_actor.id
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return approval
