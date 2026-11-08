"""Vendor onboarding and qualification.

This is the flow the pharma pitch is built on: a supplier is registered,
their regulatory documents are photographed and auto-extracted, and the
result is routed into a qualification approval workflow.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.core.access import org_column_match
from app.core.document_intelligence import DocumentIntelligence
from app.db.session import get_session
from app.models.actor import Actor
from app.models.document import ExtractedDocument, ExtractionStatus
from app.models.vendor import LicenceType, Vendor, VendorLicence, VendorStatus
from app.models.workflow import Workflow, WorkflowPhase, WorkflowState
from app.schemas.vendor import (
    DocumentOut,
    LicenceOut,
    QualificationOut,
    VendorCreate,
    VendorOut,
)

router = APIRouter(prefix="/vendors", tags=["vendors"])

logger = logging.getLogger("sangam.vendors")

# Documents are uploaded from a phone camera; anything larger is a mistake
# rather than a legitimate licence scan.
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


def _licence_out(lic: VendorLicence) -> LicenceOut:
    return LicenceOut(
        id=lic.id,
        licence_type=lic.licence_type.value,
        licence_number=lic.licence_number,
        issuing_authority=lic.issuing_authority,
        issue_date=lic.issue_date,
        expiry_date=lic.expiry_date,
        verified=lic.verified,
        extraction_confidence=lic.extraction_confidence,
        is_expired=lic.is_expired,
        days_until_expiry=lic.days_until_expiry,
    )


def _vendor_out(vendor: Vendor) -> VendorOut:
    return VendorOut(
        id=vendor.id,
        name=vendor.name,
        legal_name=vendor.legal_name,
        gstin=vendor.gstin,
        pan=vendor.pan,
        address=vendor.address,
        contact_email=vendor.contact_email,
        contact_phone=vendor.contact_phone,
        status=vendor.status.value,
        created_at=vendor.created_at,
        qualification_workflow_id=vendor.qualification_workflow_id,
        licences=[_licence_out(l) for l in vendor.licences],
        has_expired_licence=vendor.has_expired_licence,
        is_qualifiable=vendor.is_qualifiable,
    )


def _document_out(doc: ExtractedDocument) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        vendor_id=doc.vendor_id,
        filename=doc.filename,
        document_type=doc.document_type,
        status=doc.status.value,
        structured_data=doc.structured_data,
        min_confidence=doc.min_confidence,
        needs_review=doc.needs_review,
        low_confidence_fields=doc.low_confidence_fields,
        error_message=doc.error_message,
        created_at=doc.created_at,
    )


def _vendor_visible(actor: Actor):
    return (
        (Vendor.owner_actor_id == actor.id)
        & org_column_match(Vendor.organization_id, actor.zitadel_org_id)
    )


async def _get_vendor_or_404(session: AsyncSession, vendor_id: UUID, actor: Actor) -> Vendor:
    result = await session.execute(select(Vendor).where(Vendor.id == vendor_id, _vendor_visible(actor)))
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@router.post("", response_model=VendorOut, status_code=201)
async def create_vendor(
    req: VendorCreate,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    vendor = Vendor(
        id=uuid.uuid4(),
        name=req.name,
        legal_name=req.legal_name,
        gstin=req.gstin,
        pan=req.pan,
        address=req.address,
        contact_email=req.contact_email,
        contact_phone=req.contact_phone,
        status=VendorStatus.DRAFT,
        owner_actor_id=current_actor.id,
        organization_id=current_actor.zitadel_org_id,
    )
    session.add(vendor)
    await session.commit()
    await session.refresh(vendor)
    return _vendor_out(vendor)


@router.get("", response_model=List[VendorOut])
async def list_vendors(
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    stmt = select(Vendor).where(_vendor_visible(current_actor)).order_by(Vendor.created_at.desc())
    if status_filter:
        try:
            stmt = stmt.where(Vendor.status == VendorStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown status: {status_filter}")

    result = await session.execute(stmt)
    return [_vendor_out(v) for v in result.scalars().all()]


@router.get("/expiring", response_model=List[VendorOut])
async def vendors_with_expiring_licences(
    days: int = Query(90, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Vendors whose licences lapse inside the window.

    The compliance early-warning view: a lapsed CDSCO licence halts
    production, so this is what a QA lead checks daily.
    """
    result = await session.execute(select(Vendor).where(_vendor_visible(current_actor)))
    vendors = [v for v in result.scalars().all() if v.licences_expiring_within(days)]
    return [_vendor_out(v) for v in vendors]


@router.get("/{vendor_id}", response_model=VendorOut)
async def get_vendor(
    vendor_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    return _vendor_out(await _get_vendor_or_404(session, vendor_id, current_actor))


@router.get("/{vendor_id}/documents", response_model=List[DocumentOut])
async def list_vendor_documents(
    vendor_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    await _get_vendor_or_404(session, vendor_id, current_actor)
    result = await session.execute(
        select(ExtractedDocument)
        .where(ExtractedDocument.vendor_id == vendor_id)
        .order_by(ExtractedDocument.created_at.desc())
    )
    return [_document_out(d) for d in result.scalars().all()]


@router.post("/{vendor_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_vendor_document(
    vendor_id: UUID,
    file: UploadFile = File(...),
    document_type: str = Form("licence"),
    language_code: str = Form("en-IN"),
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Upload a regulatory document and extract it into structured fields.

    On a confident licence extraction a VendorLicence row is created
    automatically. Low-confidence extractions are persisted but not
    promoted to a licence: a human confirms them first, because a wrong
    expiry date here means shipping against a lapsed licence.
    """
    vendor = await _get_vendor_or_404(session, vendor_id, current_actor)

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_DOCUMENT_BYTES // (1024 * 1024)}MB limit",
        )

    di = DocumentIntelligence(session)
    doc = await di.extract(
        file_bytes=file_bytes,
        filename=file.filename or "document.pdf",
        document_type=document_type,
        vendor_id=vendor.id,
        language_code=language_code,
    )

    if doc.status == ExtractionStatus.COMPLETED and document_type == "licence":
        await _promote_to_licence(session, vendor, doc)

    return _document_out(doc)


async def _promote_to_licence(
    session: AsyncSession, vendor: Vendor, doc: ExtractedDocument
) -> Optional[VendorLicence]:
    """Create a VendorLicence from a confident extraction.

    Returns None when the extraction lacks a licence number — a licence
    record without its identifying number is not useful for an audit.
    """
    data = doc.structured_data or {}
    licence_number = data.get("licence_number")
    if not licence_number:
        return None

    raw_type = (data.get("licence_type") or "CDSCO").lower()
    try:
        licence_type = LicenceType(raw_type)
    except ValueError:
        licence_type = LicenceType.CDSCO

    licence = VendorLicence(
        id=uuid.uuid4(),
        vendor_id=vendor.id,
        licence_type=licence_type,
        licence_number=licence_number,
        issuing_authority=data.get("issuing_authority"),
        issue_date=_parse_date(data.get("issue_date")),
        expiry_date=_parse_date(data.get("expiry_date")),
        verified=False,
        extraction_confidence=doc.min_confidence,
    )
    session.add(licence)

    # Fill in vendor detail the document supplied and registration lacked.
    if not vendor.legal_name and data.get("vendor_name"):
        vendor.legal_name = data["vendor_name"]
    if not vendor.address and data.get("address"):
        vendor.address = data["address"]

    await session.commit()
    await session.refresh(licence)
    await session.refresh(vendor)
    return licence


@router.post("/{vendor_id}/documents/{document_id}/confirm", response_model=VendorOut)
async def confirm_extracted_document(
    vendor_id: UUID,
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Accept a flagged extraction after human review.

    Extractions below the confidence threshold are deliberately not
    promoted to licences automatically — a mis-read expiry date would mean
    shipping against a lapsed licence. A reviewer confirms them here, which
    creates the licence and records who accepted it.
    """
    vendor = await _get_vendor_or_404(session, vendor_id, current_actor)

    result = await session.execute(
        select(ExtractedDocument).where(
            ExtractedDocument.id == document_id,
            ExtractedDocument.vendor_id == vendor_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found for this vendor")
    if doc.status == ExtractionStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail="Extraction failed; re-upload the document rather than confirming it.",
        )
    if not doc.structured_data:
        raise HTTPException(status_code=400, detail="Document has no extracted data to confirm")

    licence = await _promote_to_licence(session, vendor, doc)
    if licence is None:
        raise HTTPException(
            status_code=400,
            detail="Extraction contains no licence number; cannot create a licence record.",
        )

    # Human confirmation is what makes a licence trustworthy, so record it.
    licence.verified = True
    doc.needs_review = False
    doc.status = ExtractionStatus.COMPLETED
    await session.commit()
    await session.refresh(vendor)

    logger.info(
        "Actor %s confirmed extraction %s -> licence %s",
        current_actor.id, doc.id, licence.id,
    )
    return _vendor_out(vendor)


@router.post("/{vendor_id}/submit-for-qualification", response_model=QualificationOut)
async def submit_for_qualification(
    vendor_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Move a vendor into the approval phase of a qualification workflow."""
    vendor = await _get_vendor_or_404(session, vendor_id, current_actor)

    if vendor.status == VendorStatus.PENDING_QUALIFICATION:
        raise HTTPException(
            status_code=409, detail="Vendor is already awaiting qualification"
        )
    if not vendor.licences:
        raise HTTPException(
            status_code=400,
            detail="Vendor has no licences on file. Upload a licence document first.",
        )
    if vendor.has_expired_licence:
        raise HTTPException(
            status_code=400,
            detail="Vendor has an expired licence and cannot be qualified.",
        )

    workflow = Workflow(
        id=uuid.uuid4(),
        name=f"Vendor qualification - {vendor.name}",
        description=(
            f"Qualification of {vendor.name} against "
            f"{len(vendor.licences)} regulatory licence(s)."
        ),
        initiator_id=current_actor.id,
        current_phase=WorkflowPhase.APPROVAL,
        state=WorkflowState.ACTIVE,
        phases=[
            WorkflowPhase.INITIATION.value,
            WorkflowPhase.APPROVAL.value,
            WorkflowPhase.VERIFICATION.value,
        ],
        extra_attributes={
            "vendor_id": str(vendor.id),
            "vendor_name": vendor.name,
            "licence_count": len(vendor.licences),
        },
    )
    session.add(workflow)

    vendor.status = VendorStatus.PENDING_QUALIFICATION
    vendor.qualification_workflow_id = workflow.id

    await session.commit()
    await session.refresh(workflow)
    await session.refresh(vendor)

    logger.info("Vendor %s submitted for qualification as workflow %s", vendor.id, workflow.id)

    return QualificationOut(
        vendor_id=vendor.id,
        workflow_id=workflow.id,
        status=vendor.status.value,
        message=f"Submitted for qualification. Awaiting approval on workflow {workflow.id}.",
    )
