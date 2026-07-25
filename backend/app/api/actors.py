from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_session
from app.models.actor import Actor
from app.schemas.actor import ActorCreate, ActorUpdate, ActorResponse

router = APIRouter(prefix="/actors", tags=["actors"])


@router.post("/", response_model=ActorResponse, status_code=status.HTTP_201_CREATED)
async def create_actor(
    data: ActorCreate,
    session: AsyncSession = Depends(get_session),
):
    actor = Actor(
        type=data.type,
        name=data.name,
        email=data.email,
        roles=data.roles,
        permissions=data.permissions,
        extra_attributes=data.extra_attributes,
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
):
    result = await session.execute(
        select(Actor).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{actor_id}", response_model=ActorResponse)
async def get_actor(
    actor_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    return actor


@router.patch("/{actor_id}", response_model=ActorResponse)
async def update_actor(
    actor_id: UUID,
    data: ActorUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(actor, field, value)

    await session.commit()
    await session.refresh(actor)
    return actor


@router.delete("/{actor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_actor(
    actor_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Actor).where(Actor.id == actor_id))
    actor = result.scalar_one_or_none()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    actor.is_active = False
    await session.commit()
