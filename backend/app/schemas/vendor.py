from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VendorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    legal_name: Optional[str] = None
    gstin: Optional[str] = Field(None, max_length=15)
    pan: Optional[str] = Field(None, max_length=10)
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class LicenceOut(BaseModel):
    id: UUID
    licence_type: str
    licence_number: str
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    verified: bool
    extraction_confidence: Optional[float] = None
    is_expired: bool = False
    days_until_expiry: Optional[int] = None


class VendorOut(BaseModel):
    id: UUID
    name: str
    legal_name: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str
    created_at: datetime
    qualification_workflow_id: Optional[UUID] = None
    licences: List[LicenceOut] = []
    has_expired_licence: bool = False
    is_qualifiable: bool = False


class DocumentOut(BaseModel):
    id: UUID
    vendor_id: Optional[UUID] = None
    filename: str
    document_type: str
    status: str
    structured_data: Optional[Dict[str, Any]] = None
    min_confidence: Optional[float] = None
    needs_review: bool
    low_confidence_fields: Dict[str, float] = {}
    error_message: Optional[str] = None
    created_at: datetime


class QualificationOut(BaseModel):
    vendor_id: UUID
    workflow_id: UUID
    status: str
    message: str
