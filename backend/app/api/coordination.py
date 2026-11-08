from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_session
from app.models.actor import Actor
from app.models.workflow import WorkflowPhase, WaitingEvent
from app.models.handoff import Handoff
from app.models.exception import ExceptionWorkflow
from app.core.coordinator import Coordinator
from app.core.audit import AuditService
from app.api.dependencies import get_current_actor
from app.core.access import load_accessible_workflow


router = APIRouter(prefix="/coordination", tags=["coordination"])


class HandoffCreateRequest(BaseModel):
    workflow_id: UUID
    from_actor_id: UUID
    to_actor_id: UUID
    artifact: Optional[str] = None
    artifact_type: Optional[str] = None
    notes: Optional[str] = None


class HandoffResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    from_actor_id: UUID
    to_actor_id: UUID
    artifact: Optional[str] = None
    artifact_type: Optional[str] = None
    notes: Optional[str] = None
    verified: bool
    verified_at: Optional[datetime] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class WaitingEventCreateRequest(BaseModel):
    workflow_id: UUID
    actor_id: UUID
    event_type: str
    reason: Optional[str] = None
    sla_minutes: Optional[int] = None


class PhaseTransitionRequest(BaseModel):
    to_phase: WorkflowPhase
    reason: Optional[str] = None


class AuditLogResponse(BaseModel):
    id: UUID
    workflow_id: Optional[UUID] = None
    actor_id: Optional[UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict] = None
    created_at: str

    class Config:
        from_attributes = True


@router.post("/transitions", response_model=dict)
async def transition_phase(
    workflow_id: UUID,
    req: PhaseTransitionRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    workflow = await load_accessible_workflow(session, current_actor.id, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    coordinator = Coordinator(session)
    try:
        workflow = await coordinator.transition_phase(
            workflow, req.to_phase, current_actor.id, req.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "id": str(workflow.id),
        "state": workflow.state.value,
        "current_phase": workflow.current_phase.value,
    }


@router.post("/handoffs", response_model=HandoffResponse, status_code=201)
async def create_handoff(
    req: HandoffCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    coordinator = Coordinator(session)
    try:
        await coordinator.authorize_handoff(
            req.workflow_id, current_actor.id, req.from_actor_id, req.to_actor_id
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    handoff = await coordinator.create_handoff(
        workflow_id=req.workflow_id,
        from_actor_id=req.from_actor_id,
        to_actor_id=req.to_actor_id,
        artifact=req.artifact,
        artifact_type=req.artifact_type,
        notes=req.notes,
    )
    return handoff


@router.post("/handoffs/{handoff_id}/verify", response_model=HandoffResponse)
async def verify_handoff(
    handoff_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    coordinator = Coordinator(session)
    try:
        handoff = await coordinator.verify_handoff(handoff_id, current_actor.id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return handoff


@router.get("/workflows/{workflow_id}/handoffs", response_model=List[HandoffResponse])
async def list_handoffs(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    workflow = await load_accessible_workflow(session, current_actor.id, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = await session.execute(
        select(Handoff).where(Handoff.workflow_id == workflow_id)
    )
    return list(result.scalars().all())


@router.post("/waiting-events", response_model=dict, status_code=201)
async def create_waiting_event(
    req: WaitingEventCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    workflow = await load_accessible_workflow(session, current_actor.id, req.workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    coordinator = Coordinator(session)
    event = await coordinator.create_waiting_event(
        workflow_id=req.workflow_id,
        actor_id=req.actor_id,
        event_type=req.event_type,
        reason=req.reason,
        sla_minutes=req.sla_minutes,
    )
    return event


@router.post("/waiting-events/{event_id}/resolve", response_model=dict)
async def resolve_waiting_event(
    event_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    coordinator = Coordinator(session)
    await coordinator.resolve_waiting_event(event_id)
    return {"status": "resolved", "event_id": str(event_id)}


@router.get("/workflows/{workflow_id}/waiting-events", response_model=List[dict])
async def list_waiting_events(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    workflow = await load_accessible_workflow(session, current_actor.id, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = await session.execute(
        select(WaitingEvent).where(WaitingEvent.workflow_id == workflow_id)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "reason": e.reason,
            "sla_deadline": e.sla_deadline.isoformat() if e.sla_deadline else None,
            "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/audit-logs", response_model=dict)
async def list_audit_logs(
    workflow_id: Optional[UUID] = Query(None),
    actor_id: Optional[UUID] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    audit = AuditService(session)
    if workflow_id:
        workflow = await load_accessible_workflow(session, current_actor.id, workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        logs = await audit.get_workflow_audit(workflow_id, limit, offset)
    elif actor_id:
        if actor_id != current_actor.id:
            raise HTTPException(status_code=404, detail="Actor not found")
        logs = await audit.get_actor_audit(actor_id, limit, offset)
    else:
        logs = await audit.get_actor_audit(current_actor.id, limit, offset)

    return {
        "items": [
            {
                "id": str(log.id),
                "workflow_id": str(log.workflow_id) if log.workflow_id else None,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": len(logs),
    }


@router.get("/workflows/{workflow_id}/exceptions", response_model=List[dict])
async def list_exceptions(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    workflow = await load_accessible_workflow(session, current_actor.id, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = await session.execute(
        select(ExceptionWorkflow).where(ExceptionWorkflow.parent_workflow_id == workflow_id)
    )
    exceptions = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "trigger": e.trigger.value,
            "severity": e.severity.value,
            "message": e.message,
            "resolution": e.resolution,
            "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
        }
        for e in exceptions
    ]
