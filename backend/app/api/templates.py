from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.models.actor import Actor
from app.templates import registry
from app.api.dependencies import get_current_actor

router = APIRouter(prefix="/templates", tags=["templates"])


class PhaseTemplateResponse(BaseModel):
    phase: str
    label: str
    description: str
    estimated_minutes: int
    auto_transition: bool


class ApprovalStepResponse(BaseModel):
    label: str
    required_roles: list[str]
    strategy: str
    condition: Optional[str] = None
    sla_minutes: Optional[int] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    phases: list[PhaseTemplateResponse]
    approval_steps: list[ApprovalStepResponse] = []
    tags: list[str] = []
    default_actor_types: list[str] = ["human", "agent"]


@router.get("/", response_model=list[TemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None),
    current_actor: Actor = Depends(get_current_actor),
):
    templates = registry.list(category=category)
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            category=t.category,
            phases=[
                PhaseTemplateResponse(
                    phase=p.phase.value,
                    label=p.label,
                    description=p.description,
                    estimated_minutes=p.estimated_minutes,
                    auto_transition=p.auto_transition,
                )
                for p in t.phases
            ],
            approval_steps=[
                ApprovalStepResponse(
                    label=a.label,
                    required_roles=[r.value for r in a.required_roles],
                    strategy=a.strategy,
                    condition=a.condition,
                    sla_minutes=a.sla_minutes,
                )
                for a in t.approval_steps
            ],
            tags=t.tags,
            default_actor_types=t.default_actor_types,
        )
        for t in templates
    ]


@router.get("/categories", response_model=list[str])
async def list_categories(
    current_actor: Actor = Depends(get_current_actor),
):
    return registry.categories()


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_actor: Actor = Depends(get_current_actor),
):
    template = registry.get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        phases=[
            PhaseTemplateResponse(
                phase=p.phase.value,
                label=p.label,
                description=p.description,
                estimated_minutes=p.estimated_minutes,
                auto_transition=p.auto_transition,
            )
            for p in template.phases
        ],
        approval_steps=[
            ApprovalStepResponse(
                label=a.label,
                required_roles=[r.value for r in a.required_roles],
                strategy=a.strategy,
                condition=a.condition,
                sla_minutes=a.sla_minutes,
            )
            for a in template.approval_steps
        ],
        tags=template.tags,
        default_actor_types=template.default_actor_types,
    )
