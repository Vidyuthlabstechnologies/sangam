from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

from app.db.session import get_session
from app.models.actor import Actor
from app.schemas.actor import ActorCreate, ActorUpdate, ActorResponse
from app.api.dependencies import get_current_actor
from app.core.access import grants_admin, is_admin

router = APIRouter(prefix="/actors", tags=["actors"])


def _visible_to(actor: Actor):
    """Self, plus rows this actor created. Listing is never the whole table."""
    return or_(Actor.id == actor.id, Actor.created_by_id == actor.id)


def _reject_privilege_escalation(actor: Actor, roles, permissions) -> None:
    if is_admin(actor):
        return
    if grants_admin(roles, permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an existing admin can assign the admin role or manage:actors",
        )


async def _visible_actor(session: AsyncSession, current: Actor, actor_id: UUID) -> Optional[Actor]:
    stmt = select(Actor).where(Actor.id == actor_id)
    if not is_admin(current):
        stmt = stmt.where(_visible_to(current))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


@router.post("/", response_model=ActorResponse, status_code=status.HTTP_201_CREATED)
async def create_actor(
    data: ActorCreate,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    _reject_privilege_escalation(current_actor, data.roles, data.permissions)
    actor = Actor(
        type=data.type,
        name=data.name,
        email=data.email,
        roles=data.roles,
        permissions=data.permissions,
        extra_attributes=data.extra_attributes,
        created_by_id=current_actor.id,
    )
    session.add(actor)
    await session.commit()
    await session.refresh(actor)
    return actor


@router.get("/", response_model=List[ActorResponse])
async def list_actors(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    result = await session.execute(
        select(Actor).where(_visible_to(current_actor)).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{actor_id}", response_model=ActorResponse)
async def get_actor(
    actor_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    actor = await _visible_actor(session, current_actor, actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    return actor


@router.patch("/{actor_id}", response_model=ActorResponse)
async def update_actor(
    actor_id: UUID,
    data: ActorUpdate,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    actor = await _visible_actor(session, current_actor, actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    update_data = data.model_dump(exclude_unset=True)
    if "roles" in update_data or "permissions" in update_data:
        _reject_privilege_escalation(
            current_actor,
            update_data.get("roles", actor.roles),
            update_data.get("permissions", actor.permissions),
        )
    # A non-admin cannot flip their own (or a colleague's) active flag to impersonate ops.
    if "is_active" in update_data and not is_admin(current_actor) and actor.id != current_actor.id:
        update_data.pop("is_active")
    for field, value in update_data.items():
        setattr(actor, field, value)

    await session.commit()
    await session.refresh(actor)
    return actor


@router.delete("/{actor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_actor(
    actor_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    actor = await _visible_actor(session, current_actor, actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    if actor.id == current_actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use account deletion to remove your own login",
        )
    actor.is_active = False
    await session.commit()
