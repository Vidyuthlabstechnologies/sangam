from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field

from app.models.actor import ActorType, Role, Permission


class ActorCreate(BaseModel):
    type: ActorType
    name: str = Field(..., min_length=1, max_length=256)
    email: Optional[str] = None
    roles: List[Role] = Field(default_factory=list)
    permissions: List[Permission] = Field(default_factory=list)
    extra_attributes: Optional[Dict[str, Any]] = None


class ActorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    email: Optional[str] = None
    roles: Optional[List[Role]] = None
    permissions: Optional[List[Permission]] = None
    extra_attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ActorResponse(BaseModel):
    id: uuid.UUID
    type: ActorType
    name: str
    email: Optional[str] = None
    roles: List[Role]
    permissions: List[Permission]
    extra_attributes: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
