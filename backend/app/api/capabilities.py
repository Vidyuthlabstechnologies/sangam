from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.models.actor import Actor
from app.core.capability_discovery import CapabilityDiscovery, CapabilityRegistration
from app.api.dependencies import get_current_actor

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


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


@router.post("/register", response_model=dict, status_code=201)
async def register_capability(
    req: RegisterCapabilityRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    discovery = CapabilityDiscovery()
    capability = CapabilityRegistration(
        id=req.id or "",
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
    )
    cap_id = await discovery.register_capability(capability)
    return {"id": cap_id, "status": "registered"}


@router.get("/search", response_model=List[CapabilityResponse])
async def search_capabilities(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50),
    service_type: Optional[str] = Query(None),
    min_trust_score: Optional[float] = Query(None, ge=0, le=1),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    current_actor: Actor = Depends(get_current_actor),
):
    discovery = CapabilityDiscovery()
    tag_list = tags.split(",") if tags else None
    results = await discovery.search_capabilities(
        query=q,
        limit=limit,
        service_type=service_type,
        min_trust_score=min_trust_score,
        tags=tag_list,
    )
    return [
        CapabilityResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            service_type=r.service_type,
            score=r.score,
            trust_score=r.trust_score,
            endpoint_url=r.endpoint_url,
            tags=r.tags,
        )
        for r in results
    ]


@router.get("/", response_model=List[CapabilityResponse])
async def list_capabilities(
    limit: int = Query(100, le=200),
    offset: int = Query(0),
    current_actor: Actor = Depends(get_current_actor),
):
    discovery = CapabilityDiscovery()
    results = await discovery.list_capabilities(limit=limit, offset=offset)
    return [
        CapabilityResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            service_type=r.service_type,
            score=r.score,
            trust_score=r.trust_score,
            endpoint_url=r.endpoint_url,
            tags=r.tags,
        )
        for r in results
    ]


@router.delete("/{cap_id}", status_code=204)
async def remove_capability(
    cap_id: str,
    current_actor: Actor = Depends(get_current_actor),
):
    discovery = CapabilityDiscovery()
    await discovery.remove_capability(cap_id)
