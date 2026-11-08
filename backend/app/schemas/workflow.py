from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.models.workflow import WorkflowPhase, WorkflowState


class ApprovalSchema(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    strategy: str
    required_actors: List[uuid.UUID]
    approved_by: List[uuid.UUID]
    rejected_by: List[uuid.UUID]
    status: str
    condition: Optional[str] = None
    expires_at: Optional[datetime] = None
    escalated_to: Optional[uuid.UUID] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class HandoffSchema(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    from_actor_id: uuid.UUID
    to_actor_id: uuid.UUID
    artifact: Optional[str] = None
    artifact_type: Optional[str] = None
    notes: Optional[str] = None
    verified: bool
    verified_at: Optional[datetime] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class ExceptionWorkflowSchema(BaseModel):
    id: uuid.UUID
    parent_workflow_id: uuid.UUID
    trigger: str
    severity: str
    message: str
    phases: List[str]
    assigned_to: Optional[uuid.UUID] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    learning: Optional[str] = None

    class Config:
        from_attributes = True


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: Optional[str] = None
    # Accepted for older clients and ignored. The server sets the initiator from the login.
    initiator_id: Optional[uuid.UUID] = None
    phases: List[WorkflowPhase] = Field(default_factory=lambda: [p for p in WorkflowPhase])
    extra_attributes: Optional[Dict[str, Any]] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = None
    state: Optional[WorkflowState] = None
    extra_attributes: Optional[Dict[str, Any]] = None


class WorkflowPhaseTransition(BaseModel):
    to_phase: WorkflowPhase
    triggered_by: uuid.UUID
    reason: Optional[str] = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    initiator_id: uuid.UUID
    current_phase: WorkflowPhase
    state: WorkflowState
    phases: List[WorkflowPhase]
    extra_attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    approvals: List[ApprovalSchema] = Field(default_factory=list)
    handoffs: List[HandoffSchema] = Field(default_factory=list)
    exceptions: List[ExceptionWorkflowSchema] = Field(default_factory=list)

    class Config:
        from_attributes = True


class WorkflowListResponse(BaseModel):
    items: List[WorkflowResponse]
    total: int
    page: int
    page_size: int


class WaitingEventCreate(BaseModel):
    workflow_id: uuid.UUID
    actor_id: uuid.UUID
    event_type: str
    reason: Optional[str] = None
    sla_deadline: Optional[datetime] = None


class WaitingEventResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    actor_id: uuid.UUID
    event_type: str
    reason: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
