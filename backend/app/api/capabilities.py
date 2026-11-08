import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actor import Actor
from app.models.capability import RegisteredCapability
from app.core.capability_discovery import CapabilityDiscovery, CapabilityRegistration
from app.api.dependencies import get_current_actor
from app.db.session import get_session

router = APIRouter(prefix="/capabilities", tags=["capabilities"])
logger = logging.getLogger("sangam.capabilities")


class RegisterCapabilityRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    service_type: str
    endpoint_url: Optional[str] = None
    tags: List[str] = []
    language: Optional[str] = None
    trust_score: float = 0.5
    avg_latency_ms: Optional[float] = None
    avg_cost_per_call: Optional[float] = None
    metadata: Optional[dict] = None


class CapabilityResponse(BaseModel):
    id: str
    name: str
    description: str
    service_type: str
    score: float
    trust_score: float
    endpoint_url: Optional[str] = None
    tags: List[str] = []


def _tenant(actor: Actor) -> str:
    return str(actor.id)


def _to_response(row: RegisteredCapability, score: float = 1.0) -> CapabilityResponse:
    return CapabilityResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        service_type=row.service_type,
        score=score,
        trust_score=row.trust_score,
        endpoint_url=row.endpoint_url,
        tags=row.tags or [],
    )


def _index() -> Optional[CapabilityDiscovery]:
    try:
        return CapabilityDiscovery()
    except Exception:
        logger.warning("Capability index is unavailable; database filter still applies")
        return None


@router.post("/register", response_model=dict, status_code=201)
async def register_capability(
    req: RegisterCapabilityRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    cap_id = req.id or str(uuid.uuid4())
    existing = await session.get(RegisteredCapability, cap_id)
    if existing is not None and existing.owner_actor_id != current_actor.id:
        raise HTTPException(status_code=404, detail="Capability not found")
    if existing is None:
        existing = RegisteredCapability(
            id=cap_id,
            owner_actor_id=current_actor.id,
            tenant_id=_tenant(current_actor),
        )
        session.add(existing)
    existing.name = req.name
    existing.description = req.description
    existing.service_type = req.service_type
    existing.endpoint_url = req.endpoint_url
    existing.tags = req.tags
    existing.language = req.language
    existing.trust_score = req.trust_score
    existing.avg_latency_ms = req.avg_latency_ms
    existing.avg_cost_per_call = req.avg_cost_per_call
    existing.metadata_json = req.metadata
    existing.tenant_id = _tenant(current_actor)
    existing.owner_actor_id = current_actor.id
    await session.commit()

    discovery = _index()
    if discovery is not None:
        try:
            await discovery.register_capability(
                CapabilityRegistration(
                    id=cap_id,
                    name=req.name,
                    description=req.description,
                    service_type=req.service_type,
                    endpoint_url=req.endpoint_url,
                    tags=req.tags,
                    language=req.language,
                    trust_score=req.trust_score,
                    avg_latency_ms=req.avg_latency_ms,
                    avg_cost_per_call=req.avg_cost_per_call,
                    metadata=req.metadata,
                ),
                tenant_id=_tenant(current_actor),
                owner_actor_id=str(current_actor.id),
            )
        except Exception:
            logger.warning("Capability %s was stored but not indexed", cap_id)
    return {"id": cap_id, "status": "registered"}


@router.get("/search", response_model=List[CapabilityResponse])
async def search_capabilities(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50),
    service_type: Optional[str] = Query(None),
    min_trust_score: Optional[float] = Query(None, ge=0, le=1),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    stmt = select(RegisteredCapability).where(RegisteredCapability.owner_actor_id == current_actor.id)
    if service_type:
        stmt = stmt.where(RegisteredCapability.service_type == service_type)
    if min_trust_score is not None:
        stmt = stmt.where(RegisteredCapability.trust_score >= min_trust_score)
    needle = f"%{q.lower()}%"
    stmt = stmt.where(
        or_(
            RegisteredCapability.name.ilike(needle),
            RegisteredCapability.description.ilike(needle),
        )
    )
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    if tags:
        wanted = {tag.strip() for tag in tags.split(",") if tag.strip()}
        rows = [row for row in rows if wanted.intersection(row.tags or [])]

    discovery = _index()
    if discovery is None:
        return [_to_response(row) for row in rows]
    try:
        indexed = await discovery.search_capabilities(
            query=q,
            limit=limit,
            service_type=service_type,
            min_trust_score=min_trust_score,
            tags=tags.split(",") if tags else None,
            tenant_id=_tenant(current_actor),
        )
    except Exception:
        logger.warning("Capability search fell back to the database")
        return [_to_response(row) for row in rows]
    by_id = {row.id: row for row in rows}
    # Index hits that are not owned in the database are dropped.
    ordered = [by_id[hit.id] for hit in indexed if hit.id in by_id]
    if not ordered:
        return [_to_response(row) for row in rows]
    scores = {hit.id: hit.score for hit in indexed}
    return [_to_response(row, scores.get(row.id, 1.0)) for row in ordered]


@router.get("/", response_model=List[CapabilityResponse])
async def list_capabilities(
    limit: int = Query(100, le=200),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    rows = (
        await session.execute(
            select(RegisteredCapability)
            .where(RegisteredCapability.owner_actor_id == current_actor.id)
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return [_to_response(row) for row in rows]


@router.delete("/{cap_id}", status_code=204)
async def remove_capability(
    cap_id: str,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    row = await session.get(RegisteredCapability, cap_id)
    if row is None or row.owner_actor_id != current_actor.id:
        raise HTTPException(status_code=404, detail="Capability not found")
    await session.delete(row)
    await session.commit()
    discovery = _index()
    if discovery is not None:
        try:
            await discovery.remove_capability(cap_id, tenant_id=_tenant(current_actor))
        except Exception:
            logger.warning("Capability %s removed from the database but not the index", cap_id)
