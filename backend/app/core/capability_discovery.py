from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    SearchParams,
)

from app.config import settings


@dataclass
class CapabilityRegistration:
    id: str
    name: str
    description: str
    service_type: str  # api, mcp, agent, webhook
    endpoint_url: Optional[str] = None
    tags: List[str] = None
    language: Optional[str] = None
    trust_score: float = 0.5
    avg_latency_ms: Optional[float] = None
    avg_cost_per_call: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CapabilitySearchResult:
    id: str
    name: str
    description: str
    service_type: str
    score: float
    trust_score: float
    endpoint_url: Optional[str] = None
    tags: List[str] = None


class CapabilityDiscovery:
    def __init__(self):
        self.client = QdrantClient(
            url=settings.qdrant_url,
            timeout=5,
        )
        self.collection_name = settings.qdrant_collection
        self._ensure_collection()

    @staticmethod
    def _tenant_condition(tenant_id: str) -> FieldCondition:
        return FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]

        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE,
                ),
            )

    def _embed_text(self, text: str) -> List[float]:
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = [b / 255.0 for b in hash_bytes[:384]]
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    async def register_capability(
        self,
        capability: CapabilityRegistration,
        *,
        tenant_id: str,
        owner_actor_id: str,
    ) -> str:
        cap_id = capability.id or str(uuid.uuid4())

        search_text = f"{capability.name} {capability.description} {' '.join(capability.tags or [])}"
        vector = self._embed_text(search_text)

        payload = {
            "id": cap_id,
            "name": capability.name,
            "description": capability.description,
            "service_type": capability.service_type,
            "endpoint_url": capability.endpoint_url,
            "tags": capability.tags or [],
            "language": capability.language,
            "trust_score": capability.trust_score,
            "avg_latency_ms": capability.avg_latency_ms,
            "avg_cost_per_call": capability.avg_cost_per_call,
            "metadata": capability.metadata or {},
            "tenant_id": tenant_id,
            "owner_actor_id": owner_actor_id,
            "registered_at": datetime.utcnow().isoformat(),
        }

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=cap_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        return cap_id

    async def search_capabilities(
        self,
        query: str,
        limit: int = 10,
        service_type: Optional[str] = None,
        min_trust_score: Optional[float] = None,
        tags: Optional[List[str]] = None,
        *,
        tenant_id: str,
    ) -> List[CapabilitySearchResult]:
        vector = self._embed_text(query)

        conditions = [self._tenant_condition(tenant_id)]
        if service_type:
            conditions.append(
                FieldCondition(
                    key="service_type",
                    match=MatchValue(value=service_type),
                )
            )
        if min_trust_score is not None:
            conditions.append(
                FieldCondition(
                    key="trust_score",
                    range=Range(gte=min_trust_score),
                )
            )
        if tags:
            for tag in tags:
                conditions.append(
                    FieldCondition(
                        key="tags",
                        match=MatchValue(value=tag),
                    )
                )

        query_filter = Filter(must=conditions)

        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter,
            search_params=SearchParams(hnsw_ef=128, exact=False),
        )

        return [
            CapabilitySearchResult(
                id=point.payload.get("id", ""),
                name=point.payload.get("name", ""),
                description=point.payload.get("description", ""),
                service_type=point.payload.get("service_type", ""),
                score=point.score,
                trust_score=point.payload.get("trust_score", 0.0),
                endpoint_url=point.payload.get("endpoint_url"),
                tags=point.payload.get("tags", []),
            )
            for point in results
        ]

    async def remove_capability(self, cap_id: str, *, tenant_id: str):
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[cap_id],
            with_payload=True,
        )
        if points and (points[0].payload or {}).get("tenant_id") not in (None, tenant_id):
            return
        if points and (points[0].payload or {}).get("tenant_id") != tenant_id:
            return
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[cap_id],
        )

    async def list_capabilities(
        self,
        limit: int = 100,
        offset: int = 0,
        *,
        tenant_id: str,
    ) -> List[CapabilitySearchResult]:
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=[self._tenant_condition(tenant_id)]),
            limit=limit,
            offset=offset,
        )
        points = results[0]
        return [
            CapabilitySearchResult(
                id=point.payload.get("id", ""),
                name=point.payload.get("name", ""),
                description=point.payload.get("description", ""),
                service_type=point.payload.get("service_type", ""),
                score=1.0,
                trust_score=point.payload.get("trust_score", 0.0),
                endpoint_url=point.payload.get("endpoint_url"),
                tags=point.payload.get("tags", []),
            )
            for point in points
        ]
