from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from app.models.workflow import WorkflowPhase
from app.models.actor import Role


@dataclass
class ApprovalStepTemplate:
    label: str
    required_roles: List[Role]
    strategy: str = "all"
    condition: Optional[str] = None
    sla_minutes: Optional[int] = None


@dataclass
class PhaseTemplate:
    phase: WorkflowPhase
    label: str
    description: str
    estimated_minutes: int = 60
    required_roles: List[Role] = field(default_factory=list)
    auto_transition: bool = True


@dataclass
class WorkflowTemplate:
    id: str
    name: str
    description: str
    category: str
    phases: List[PhaseTemplate]
    approval_steps: List[ApprovalStepTemplate] = field(default_factory=list)
    default_actor_types: List[str] = field(default_factory=lambda: ["human", "agent"])
    tags: List[str] = field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True


class TemplateRegistry:
    def __init__(self):
        self._templates: Dict[str, WorkflowTemplate] = {}

    def register(self, template: WorkflowTemplate):
        self._templates[template.id] = template

    def get(self, template_id: str) -> Optional[WorkflowTemplate]:
        return self._templates.get(template_id)

    def list(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        if category:
            return [t for t in self._templates.values() if t.category == category and t.is_active]
        return [t for t in self._templates.values() if t.is_active]

    def categories(self) -> List[str]:
        return list({t.category for t in self._templates.values()})
