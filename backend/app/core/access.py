"""Application-layer visibility for the single shared deployment.

Tests run on SQLite, so this does not turn on Postgres row-level security.
A row is visible when the actor participates and the Zitadel organization
stamped on the row matches the organization in the caller's token. A miss
is a 404 so ids cannot be probed. Actors with no organization only see
legacy rows that also have none.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actor import Actor, Permission, Role
from app.models.approval import Approval
from app.models.exception import ExceptionWorkflow
from app.models.handoff import Handoff
from app.models.workflow import WaitingEvent, Workflow

_ADMIN = Role.ADMIN.value
_MANAGE_ACTORS = Permission.MANAGE_ACTORS.value


def role_values(actor: Actor) -> set[str]:
    return {getattr(role, "value", role) for role in (actor.roles or [])}


def permission_values(actor: Actor) -> set[str]:
    return {getattr(perm, "value", perm) for perm in (actor.permissions or [])}


def is_admin(actor: Actor) -> bool:
    return _ADMIN in role_values(actor)


def grants_admin(roles, permissions) -> bool:
    role_set = {getattr(role, "value", role) for role in (roles or [])}
    perm_set = {getattr(perm, "value", perm) for perm in (permissions or [])}
    return _ADMIN in role_set or _MANAGE_ACTORS in perm_set


def org_column_match(column, organization_id: Optional[str]):
    """SQL predicate: same Zitadel organization, or both unset for legacy rows."""
    if organization_id:
        return column == organization_id
    return column.is_(None)


def workflow_visibility(actor_id: UUID, organization_id: Optional[str] = None):
    """SQL predicate: workflows this actor participates in, inside their organization."""
    actor_s = str(actor_id)
    mentioned = or_(
        cast(Approval.required_actors, String).contains(actor_s),
        cast(Approval.approved_by, String).contains(actor_s),
        cast(Approval.rejected_by, String).contains(actor_s),
        Approval.escalated_to == actor_id,
    )
    participation = or_(
        Workflow.initiator_id == actor_id,
        Workflow.id.in_(select(Approval.workflow_id).where(mentioned)),
        Workflow.id.in_(
            select(Handoff.workflow_id).where(
                or_(Handoff.from_actor_id == actor_id, Handoff.to_actor_id == actor_id)
            )
        ),
        Workflow.id.in_(select(WaitingEvent.workflow_id).where(WaitingEvent.actor_id == actor_id)),
        Workflow.id.in_(
            select(ExceptionWorkflow.parent_workflow_id).where(ExceptionWorkflow.assigned_to == actor_id)
        ),
    )
    return participation & org_column_match(Workflow.organization_id, organization_id)


def workflows_visible_to(actor: Actor):
    return workflow_visibility(actor.id, actor.zitadel_org_id)


async def actor_can_access_workflow_id(session: AsyncSession, actor_id: UUID, workflow_id: UUID) -> bool:
    return await load_accessible_workflow(session, actor_id, workflow_id) is not None


async def load_accessible_workflow(
    session: AsyncSession, actor_id: UUID, workflow_id: UUID
) -> Workflow | None:
    actor = await session.get(Actor, actor_id)
    if actor is None or not actor.is_active:
        return None
    result = await session.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            workflow_visibility(actor_id, actor.zitadel_org_id),
        )
    )
    return result.scalar_one_or_none()


async def other_participants(session: AsyncSession, workflow: Workflow, actor_id: UUID) -> set[UUID]:
    """Other actors who still have a stake in this workflow."""
    found: set[UUID] = set()
    if workflow.initiator_id != actor_id:
        found.add(workflow.initiator_id)

    approvals = (
        await session.execute(select(Approval).where(Approval.workflow_id == workflow.id))
    ).scalars().all()
    for approval in approvals:
        for bucket in (approval.required_actors, approval.approved_by, approval.rejected_by):
            for raw in bucket or []:
                try:
                    other = UUID(str(raw))
                except ValueError:
                    continue
                if other != actor_id:
                    found.add(other)
        if approval.escalated_to and approval.escalated_to != actor_id:
            found.add(approval.escalated_to)

    handoffs = (
        await session.execute(select(Handoff).where(Handoff.workflow_id == workflow.id))
    ).scalars().all()
    for handoff in handoffs:
        for other in (handoff.from_actor_id, handoff.to_actor_id):
            if other != actor_id:
                found.add(other)

    waiting = (
        await session.execute(select(WaitingEvent).where(WaitingEvent.workflow_id == workflow.id))
    ).scalars().all()
    for event in waiting:
        if event.actor_id != actor_id:
            found.add(event.actor_id)

    exceptions = (
        await session.execute(
            select(ExceptionWorkflow).where(ExceptionWorkflow.parent_workflow_id == workflow.id)
        )
    ).scalars().all()
    for exc in exceptions:
        if exc.assigned_to and exc.assigned_to != actor_id:
            found.add(exc.assigned_to)
    return found
