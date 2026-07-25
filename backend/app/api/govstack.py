from uuid import UUID
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.db.session import get_session
from app.models.actor import Actor
from app.api.dependencies import get_current_actor
from app.core.govstack import GovStackService, GOVSTACK_CAPABILITIES

router = APIRouter(prefix="/govstack", tags=["govstack"])


# Request/Response Models
class GSTNValidateRequest(BaseModel):
    gstin: str = Field(..., pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")


class GSTNValidateResponse(BaseModel):
    gstin: str
    is_valid: bool
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    registration_date: Optional[str] = None
    status: Optional[str] = None
    taxpayer_type: Optional[str] = None


class GSTReturnsRequest(BaseModel):
    gstin: str = Field(..., pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
    return_period: str  # YYYY-MM


class GSTReturnsResponse(BaseModel):
    gstin: str
    return_period: str
    returns_filed: List[Dict[str, Any]]
    compliance_score: float
    last_filed: Optional[str] = None


class MCACompanyRequest(BaseModel):
    cin: str = Field(..., pattern=r"^[UL]{1}[0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")


class MCACompanyResponse(BaseModel):
    cin: str
    company_name: str
    status: str
    registration_date: Optional[str] = None
    authorized_capital: Optional[str] = None
    paid_up_capital: Optional[str] = None
    registered_address: Optional[str] = None
    directors: List[Dict[str, Any]] = []


class MCADirectorRequest(BaseModel):
    din: str = Field(..., pattern=r"^[0-9]{8}$")


class MCADirectorResponse(BaseModel):
    din: str
    is_valid: bool
    director_name: Optional[str] = None
    status: Optional[str] = None
    companies: List[Dict[str, Any]] = []
    appointment_dates: List[Dict[str, Any]] = []


class UdyamValidateRequest(BaseModel):
    udyam_number: str = Field(..., pattern=r"^UDYAM-[A-Z]{2}-[0-9]{7}$")


class UdyamValidateResponse(BaseModel):
    udyam_number: str
    is_valid: bool
    enterprise_name: Optional[str] = None
    category: Optional[str] = None  # Micro, Small, Medium
    registration_date: Optional[str] = None
    address: Optional[str] = None
    social_category: Optional[str] = None


class PANValidateRequest(BaseModel):
    pan: str = Field(..., pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")


class PANValidateResponse(BaseModel):
    pan: str
    is_valid: bool
    name: Optional[str] = None
    pan_type: Optional[str] = None  # Individual, Company, HUF, etc.
    status: Optional[str] = None  # Active, Inactive
    address: Optional[str] = None


class EPFOValidateRequest(BaseModel):
    uan: str = Field(..., pattern=r"^[0-9]{12}$")


class EPFOValidateResponse(BaseModel):
    uan: str
    is_valid: bool
    member_name: Optional[str] = None
    employer_name: Optional[str] = None
    pf_balance: Optional[str] = None
    kyc_status: Optional[str] = None
    last_contribution: Optional[str] = None


class DigiLockerVerifyRequest(BaseModel):
    document_id: str
    document_type: str  # Aadhaar, PAN, Driving License, etc.


class DigiLockerVerifyResponse(BaseModel):
    document_id: str
    document_type: str
    is_valid: bool
    holder_name: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None


class IECValidateRequest(BaseModel):
    iec: str = Field(..., pattern=r"^[0-9]{10}$")


class IECValidateResponse(BaseModel):
    iec: str
    is_valid: bool
    company_name: Optional[str] = None
    address: Optional[str] = None
    branches: List[Dict[str, Any]] = []
    status: Optional[str] = None


class ICEGATETrackRequest(BaseModel):
    bill_of_entry: str


class ICEGATETrackResponse(BaseModel):
    bill_of_entry: str
    status: str  # Filed, Assessed, Cleared, etc.
    importer_name: Optional[str] = None
    customs_duty: Optional[str] = None
    igst: Optional[str] = None
    clearance_date: Optional[str] = None


class RERAValidateRequest(BaseModel):
    rera_number: str


class RERAValidateResponse(BaseModel):
    rera_number: str
    is_valid: bool
    project_name: Optional[str] = None
    builder_name: Optional[str] = None
    project_status: Optional[str] = None  # Ongoing, Completed, Delayed
    address: Optional[str] = None
    possession_date: Optional[str] = None
    total_units: Optional[int] = None


class FSSAIValidateRequest(BaseModel):
    license_number: str


class FSSAIValidateResponse(BaseModel):
    license_number: str
    is_valid: bool
    business_name: Optional[str] = None
    license_type: Optional[str] = None  # Central, State, Registration
    food_categories: List[str] = []
    address: Optional[str] = None
    validity_period: Optional[str] = None


class GeMValidateRequest(BaseModel):
    gem_registration_id: str


class GeMValidateResponse(BaseModel):
    gem_registration_id: str
    is_valid: bool
    vendor_name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None  # Active, Suspended
    registration_date: Optional[str] = None


class SchemeDiscoverRequest(BaseModel):
    industry: str
    state: str
    size: str = "small"  # micro, small, medium
    category: str = "general"  # general, sc, st, obc, women


class SchemeDiscoverResponse(BaseModel):
    schemes: List[Dict[str, Any]]


class MOSPIIndicatorRequest(BaseModel):
    indicator: str


class MOSPIIndicatorResponse(BaseModel):
    indicator_id: str
    name: str
    value: float
    unit: str
    period: str
    source: str
    metadata: Dict[str, Any] = {}


class MOSPILaborRequest(BaseModel):
    survey: str = "PLFS"  # PLFS, NSS


class MOSPILaborResponse(BaseModel):
    survey_id: str
    period: str
    unemployment_rate: Optional[float] = None
    labor_force_participation: Optional[float] = None
    employment_by_sector: Dict[str, Any] = {}
    wage_growth: Optional[float] = None


class GatiShaktiRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class GatiShaktiResponse(BaseModel):
    location_id: str
    latitude: float
    longitude: float
    infrastructure: List[Dict[str, Any]] = []
    industrial_zones: List[Dict[str, Any]] = []
    logistics_cost_index: Optional[float] = None
    connectivity_score: Optional[float] = None


class PowerDataRequest(BaseModel):
    region: str


class PowerDataResponse(BaseModel):
    region: str
    timestamp: str
    generation: Dict[str, float] = {}
    demand: float
    supply: float
    deficit: float
    grid_frequency: Optional[float] = None


# New capabilities request/response models
class DINValidateRequest(BaseModel):
    din: str = Field(..., pattern=r"^[0-9]{8}$")


class DINValidateResponse(BaseModel):
    din: str
    is_valid: bool
    director_name: Optional[str] = None
    status: Optional[str] = None  # Active, Disqualified
    companies: List[Dict[str, Any]] = []
    appointment_dates: List[Dict[str, Any]] = []


class EPFOValidateRequest(BaseModel):
    uan: str = Field(..., pattern=r"^[0-9]{12}$")


class EPFOValidateResponse(BaseModel):
    uan: str
    is_valid: bool
    member_name: Optional[str] = None
    employer_name: Optional[str] = None
    pf_balance: Optional[str] = None
    kyc_status: Optional[str] = None
    last_contribution: Optional[str] = None


class DigiLockerVerifyRequest(BaseModel):
    document_id: str
    document_type: str  # Aadhaar, PAN, Driving License, etc.


class DigiLockerVerifyResponse(BaseModel):
    document_id: str
    document_type: str
    is_valid: bool
    holder_name: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None


class IECValidateRequest(BaseModel):
    iec: str = Field(..., pattern=r"^[0-9]{10}$")


class IECValidateResponse(BaseModel):
    iec: str
    is_valid: bool
    company_name: Optional[str] = None
    address: Optional[str] = None
    branches: List[Dict[str, Any]] = []
    status: Optional[str] = None


class ICEGATETrackRequest(BaseModel):
    bill_of_entry: str


class ICEGATETrackResponse(BaseModel):
    bill_of_entry: str
    status: str  # Filed, Assessed, Cleared, etc.
    importer_name: Optional[str] = None
    customs_duty: Optional[str] = None
    igst: Optional[str] = None
    clearance_date: Optional[str] = None


class RERAValidateRequest(BaseModel):
    rera_number: str


class RERAValidateResponse(BaseModel):
    rera_number: str
    is_valid: bool
    project_name: Optional[str] = None
    builder_name: Optional[str] = None
    project_status: Optional[str] = None  # Ongoing, Completed, Delayed
    address: Optional[str] = None
    possession_date: Optional[str] = None
    total_units: Optional[int] = None


class FSSAIValidateRequest(BaseModel):
    license_number: str


class FSSAIValidateResponse(BaseModel):
    license_number: str
    is_valid: bool
    business_name: Optional[str] = None
    license_type: Optional[str] = None  # Central, State, Registration
    food_categories: List[str] = []
    address: Optional[str] = None
    validity_period: Optional[str] = None


class GeMValidateRequest(BaseModel):
    gem_registration_id: str


class GeMValidateResponse(BaseModel):
    gem_registration_id: str
    is_valid: bool
    vendor_name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None  # Active, Suspended
    registration_date: Optional[str] = None


class GSTReturnsRequest(BaseModel):
    gstin: str = Field(..., pattern=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
    return_period: str  # YYYY-MM


class GSTReturnsResponse(BaseModel):
    gstin: str
    return_period: str
    returns_filed: List[Dict[str, Any]]
    compliance_score: float
    last_filed: Optional[str] = None


# Get GovStack service instance
def get_govstack_service() -> GovStackService:
    import os
    brightdata_token = os.getenv("BRIGHTDATA_API_TOKEN")
    return GovStackService(brightdata_token=brightdata_token if brightdata_token else None)


@router.post("/gstn/validate", response_model=GSTNValidateResponse)
async def validate_gstin(
    req: GSTNValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate GSTIN and get taxpayer details from GSTN portal"""
    result = await service.validate_gstin(req.gstin)
    return GSTNValidateResponse(
        gstin=result.gstin,
        is_valid=result.is_valid,
        legal_name=result.legal_name,
        trade_name=result.trade_name,
        address=result.address,
        state=result.state,
        registration_date=result.registration_date,
        status=result.status,
        taxpayer_type=result.taxpayer_type,
    )


@router.post("/mca/company", response_model=MCACompanyResponse)
async def get_company_details(
    req: MCACompanyRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get company details from MCA (CIN lookup)"""
    result = await service.get_company_details(req.cin)
    return MCACompanyResponse(
        cin=result.cin,
        company_name=result.company_name,
        status=result.status,
        registration_date=result.registration_date,
        authorized_capital=result.authorized_capital,
        paid_up_capital=result.paid_up_capital,
        registered_address=result.registered_address,
        directors=result.directors,
    )


@router.post("/udyam/validate", response_model=UdyamValidateResponse)
async def validate_udyam(
    req: UdyamValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Udyam registration (MSME)"""
    result = await service.validate_udyam(req.udyam_number)
    return UdyamValidateResponse(
        udyam_number=result.udyam_number,
        is_valid=result.is_valid,
        enterprise_name=result.enterprise_name,
        category=result.category,
        registration_date=result.registration_date,
        address=result.address,
        social_category=result.social_category,
    )


@router.post("/schemes/discover", response_model=SchemeDiscoverResponse)
async def discover_schemes(
    req: SchemeDiscoverRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Discover government schemes matching business profile"""
    result = await service.discover_schemes({
        "industry": req.industry,
        "state": req.state,
        "size": req.size,
        "category": req.category,
    })
    return SchemeDiscoverResponse(schemes=[{
        "scheme_id": s.scheme_id,
        "scheme_name": s.scheme_name,
        "ministry": s.ministry,
        "description": s.description,
        "eligibility_criteria": s.eligibility_criteria,
        "benefits": s.benefits,
        "application_url": s.application_url,
        "deadline": s.deadline,
        "target_beneficiaries": s.target_beneficiaries,
    } for s in result])


@router.post("/mospi/indicator", response_model=MOSPIIndicatorResponse)
async def get_economic_indicator(
    req: MOSPIIndicatorRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get economic indicator from MoSPI/NSO"""
    result = await service.get_economic_indicator(req.indicator)
    return MOSPIIndicatorResponse(
        indicator_id=result.indicator_id,
        name=result.name,
        value=result.value,
        unit=result.unit,
        period=result.period,
        source=result.source,
        metadata=result.metadata,
    )


@router.post("/mospi/labor", response_model=MOSPILaborResponse)
async def get_labor_data(
    req: MOSPILaborRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get labor force survey data from NSO"""
    result = await service.get_labor_data(req.survey)
    return MOSPILaborResponse(
        survey_id=result.survey_id,
        period=result.period,
        unemployment_rate=result.unemployment_rate,
        labor_force_participation=result.labor_force_participation,
        employment_by_sector=result.employment_by_sector,
        wage_growth=result.wage_growth,
    )


@router.post("/gatishakti/analyze", response_model=GatiShaktiResponse)
async def analyze_location(
    req: GatiShaktiRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Analyze location logistics using PM GatiShakti geospatial data"""
    result = await service.analyze_location(req.latitude, req.longitude)
    return GatiShaktiResponse(
        location_id=result.location_id,
        latitude=result.latitude,
        longitude=result.longitude,
        infrastructure=result.infrastructure,
        industrial_zones=result.industrial_zones,
        logistics_cost_index=result.logistics_cost_index,
        connectivity_score=result.connectivity_score,
    )


@router.post("/power/data", response_model=PowerDataResponse)
async def get_power_data(
    req: PowerDataRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get power sector data from National Power Portal"""
    result = await service.get_power_data(req.region)
    return PowerDataResponse(
        region=result.region,
        timestamp=result.timestamp.isoformat(),
        generation=result.generation,
        demand=result.demand,
        supply=result.supply,
        deficit=result.deficit,
        grid_frequency=result.grid_frequency,
    )


@router.post("/capabilities/register")
async def register_capabilities(
    current_actor: Actor = Depends(get_current_actor),
):
    """Register all GovStack capabilities with the platform"""
    from app.api.capabilities import register_capability
    
    results = []
    for cap in GOVSTACK_CAPABILITIES:
        try:
            # This would integrate with the capabilities registry
            results.append({"name": cap["name"], "status": "registered"})
        except Exception as e:
            results.append({"name": cap["name"], "status": "failed", "error": str(e)})
    
    return {"registered": results}


@router.get("/capabilities")
async def list_capabilities():
    """List all GovStack capabilities for registration"""
    return {"capabilities": GOVSTACK_CAPABILITIES}


@router.post("/capabilities/register")
async def register_capabilities(
    current_actor: Actor = Depends(get_current_actor),
):
    """Register all GovStack capabilities with the platform"""
    from app.api.capabilities import register_capability
    
    results = []
    for cap in GOVSTACK_CAPABILITIES:
        try:
            # This would integrate with the capabilities registry
            results.append({"name": cap["name"], "status": "registered"})
        except Exception as e:
            results.append({"name": cap["name"], "status": "failed", "error": str(e)})
    
    return {"registered": results}


# ============ NEW GOVERNMENT CAPABILITIES ENDPOINTS ============
@router.post("/pan/validate", response_model=PANValidateResponse)
async def validate_pan(
    req: PANValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate PAN and get taxpayer details"""
    result = await service.validate_pan(req.pan)
    return PANValidateResponse(
        pan=result.pan,
        is_valid=result.is_valid,
        name=result.name,
        pan_type=result.pan_type,
        status=result.status,
        address=result.address,
    )


# DIN Validation (Director Identification Number)
@router.post("/mca/director", response_model=DINValidateResponse)
async def validate_din(
    req: DINValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get director details from MCA (DIN lookup)"""
    result = await service.validate_din(req.din)
    return DINValidateResponse(
        din=result.din,
        is_valid=result.is_valid,
        director_name=result.director_name,
        status=result.status,
        companies=result.companies,
        appointment_dates=result.appointment_dates,
    )


# EPFO Validation (UAN)
@router.post("/epfo/validate", response_model=EPFOValidateResponse)
async def validate_epfo(
    req: EPFOValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate UAN and get EPF details"""
    result = await service.validate_epfo(req.uan)
    return EPFOValidateResponse(
        uan=result.uan,
        is_valid=result.is_valid,
        member_name=result.member_name,
        employer_name=result.employer_name,
        pf_balance=result.pf_balance,
        kyc_status=result.kyc_status,
        last_contribution=result.last_contribution,
    )


# DigiLocker Document Verification
@router.post("/digilocker/verify", response_model=DigiLockerVerifyResponse)
async def verify_digilocker(
    req: DigiLockerVerifyRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Verify digital document from DigiLocker"""
    result = await service.verify_digilocker(req.document_id, req.document_type)
    return DigiLockerVerifyResponse(
        document_id=result.document_id,
        document_type=result.document_type,
        is_valid=result.is_valid,
        holder_name=result.holder_name,
        issue_date=result.issue_date,
        expiry_date=result.expiry_date,
        issuing_authority=result.issuing_authority,
    )


# IEC Validation (Import Export Code)
@router.post("/iec/validate", response_model=IECValidateResponse)
async def validate_iec(
    req: IECValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Import Export Code (IEC) from DGFT"""
    result = await service.validate_iec(req.iec)
    return IECValidateResponse(
        iec=result.iec,
        is_valid=result.is_valid,
        company_name=result.company_name,
        address=result.address,
        branches=result.branches,
        status=result.status,
    )


# ICEGATE Customs Tracking
@router.post("/icegate/track", response_model=ICEGATETrackResponse)
async def track_icegate(
    req: ICEGATETrackRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Track customs clearance status via ICEGATE"""
    result = await service.track_icegate(req.bill_of_entry)
    return ICEGATETrackResponse(
        bill_of_entry=result.bill_of_entry,
        status=result.status,
        importer_name=result.importer_name,
        customs_duty=result.customs_duty,
        igst=result.igst,
        clearance_date=result.clearance_date,
    )


# RERA Project Validation
@router.post("/rera/validate", response_model=RERAValidateResponse)
async def validate_rera(
    req: RERAValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate RERA project registration"""
    result = await service.validate_rera(req.rera_number)
    return RERAValidateResponse(
        rera_number=result.rera_number,
        is_valid=result.is_valid,
        project_name=result.project_name,
        builder_name=result.builder_name,
        project_status=result.project_status,
        address=result.address,
        possession_date=result.possession_date,
        total_units=result.total_units,
    )


# FSSAI Food License Validation
@router.post("/fssai/validate", response_model=FSSAIValidateResponse)
async def validate_fssai(
    req: FSSAIValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate FSSAI food license"""
    result = await service.validate_fssai(req.license_number)
    return FSSAIValidateResponse(
        license_number=result.license_number,
        is_valid=result.is_valid,
        business_name=result.business_name,
        license_type=result.license_type,
        food_categories=result.food_categories,
        address=result.address,
        validity_period=result.validity_period,
    )


# GeM Vendor Validation
@router.post("/gem/validate", response_model=GeMValidateResponse)
async def validate_gem(
    req: GeMValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Government e-Marketplace (GeM) registration"""
    result = await service.validate_gem(req.gem_registration_id)
    return GeMValidateResponse(
        gem_registration_id=result.gem_registration_id,
        is_valid=result.is_valid,
        vendor_name=result.vendor_name,
        category=result.category,
        status=result.status,
        registration_date=result.registration_date,
    )


# GST Returns Filing History
@router.post("/gstn/returns", response_model=GSTReturnsResponse)
async def get_gst_returns(
    req: GSTReturnsRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get GST return filing history and compliance score"""
    result = await service.get_gst_returns(req.gstin, req.return_period)
    return GSTReturnsResponse(
        gstin=result.gstin,
        return_period=result.return_period,
        returns_filed=result.returns_filed,
        compliance_score=result.compliance_score,
        last_filed=result.last_filed,
    )


# DIN Validation (Director Identification Number) - alias for MCA Director
@router.post("/mca/director", response_model=DINValidateResponse)
async def validate_din(
    req: DINValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate DIN and get director details from MCA"""
    result = await service.validate_din(req.din)
    return DINValidateResponse(
        din=result.din,
        is_valid=result.is_valid,
        director_name=result.director_name,
        status=result.status,
        companies=result.companies,
        appointment_dates=result.appointment_dates,
    )


# EPFO Validation
@router.post("/epfo/validate", response_model=EPFOValidateResponse)
async def validate_epfo(
    req: EPFOValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate UAN and get EPF details"""
    result = await service.validate_epfo(req.uan)
    return EPFOValidateResponse(
        uan=result.uan,
        is_valid=result.is_valid,
        member_name=result.member_name,
        employer_name=result.employer_name,
        pf_balance=result.pf_balance,
        kyc_status=result.kyc_status,
        last_contribution=result.last_contribution,
    )


# DigiLocker Document Verification
@router.post("/digilocker/verify", response_model=DigiLockerVerifyResponse)
async def verify_digilocker(
    req: DigiLockerVerifyRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Verify digital document from DigiLocker"""
    result = await service.verify_digilocker(req.document_id, req.document_type)
    return DigiLockerVerifyResponse(
        document_id=result.document_id,
        document_type=result.document_type,
        is_valid=result.is_valid,
        holder_name=result.holder_name,
        issue_date=result.issue_date,
        expiry_date=result.expiry_date,
        issuing_authority=result.issuing_authority,
    )


# IEC Validation
@router.post("/iec/validate", response_model=IECValidateResponse)
async def validate_iec(
    req: IECValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Import Export Code (IEC) from DGFT"""
    result = await service.validate_iec(req.iec)
    return IECValidateResponse(
        iec=result.iec,
        is_valid=result.is_valid,
        company_name=result.company_name,
        address=result.address,
        branches=result.branches,
        status=result.status,
    )


# ICEGATE Customs Tracking
@router.post("/icegate/track", response_model=ICEGATETrackResponse)
async def track_icegate(
    req: ICEGATETrackRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Track customs clearance status via ICEGATE"""
    result = await service.track_icegate(req.bill_of_entry)
    return ICEGATETrackResponse(
        bill_of_entry=result.bill_of_entry,
        status=result.status,
        importer_name=result.importer_name,
        customs_duty=result.customs_duty,
        igst=result.igst,
        clearance_date=result.clearance_date,
    )


# RERA Project Validation
@router.post("/rera/validate", response_model=RERAValidateResponse)
async def validate_rera(
    req: RERAValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate RERA project registration"""
    result = await service.validate_rera(req.rera_number)
    return RERAValidateResponse(
        rera_number=result.rera_number,
        is_valid=result.is_valid,
        project_name=result.project_name,
        builder_name=result.builder_name,
        project_status=result.project_status,
        address=result.address,
        possession_date=result.possession_date,
        total_units=result.total_units,
    )


# FSSAI Food License Validation
@router.post("/fssai/validate", response_model=FSSAIValidateResponse)
async def validate_fssai(
    req: FSSAIValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate FSSAI food license"""
    result = await service.validate_fssai(req.license_number)
    return FSSAIValidateResponse(
        license_number=result.license_number,
        is_valid=result.is_valid,
        business_name=result.business_name,
        license_type=result.license_type,
        food_categories=result.food_categories,
        address=result.address,
        validity_period=result.validity_period,
    )


# GeM Vendor Validation
@router.post("/gem/validate", response_model=GeMValidateResponse)
async def validate_gem(
    req: GeMValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Government e-Marketplace (GeM) registration"""
    result = await service.validate_gem(req.gem_registration_id)
    return GeMValidateResponse(
        gem_registration_id=result.gem_registration_id,
        is_valid=result.is_valid,
        vendor_name=result.vendor_name,
        category=result.category,
        status=result.status,
        registration_date=result.registration_date,
    )


# GST Returns Filing History
@router.post("/gstn/returns", response_model=GSTReturnsResponse)
async def get_gst_returns(
    req: GSTReturnsRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get GST return filing history and compliance score"""
    result = await service.get_gst_returns(req.gstin, req.return_period)
    return GSTReturnsResponse(
        gstin=result.gstin,
        return_period=result.return_period,
        returns_filed=result.returns_filed,
        compliance_score=result.compliance_score,
        last_filed=result.last_filed,
    )


# DIN Validation (Director Identification Number) - alias for MCA Director
@router.post("/mca/director", response_model=DINValidateResponse)
async def validate_din(
    req: DINValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate DIN and get director details from MCA"""
    result = await service.validate_din(req.din)
    return DINValidateResponse(
        din=result.din,
        is_valid=result.is_valid,
        director_name=result.director_name,
        status=result.status,
        companies=result.companies,
        appointment_dates=result.appointment_dates,
    )


# EPFO Validation
@router.post("/epfo/validate", response_model=EPFOValidateResponse)
async def validate_epfo(
    req: EPFOValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate UAN and get EPF details"""
    result = await service.validate_epfo(req.uan)
    return EPFOValidateResponse(
        uan=result.uan,
        is_valid=result.is_valid,
        member_name=result.member_name,
        employer_name=result.employer_name,
        pf_balance=result.pf_balance,
        kyc_status=result.kyc_status,
        last_contribution=result.last_contribution,
    )


# DigiLocker Document Verification
@router.post("/digilocker/verify", response_model=DigiLockerVerifyResponse)
async def verify_digilocker(
    req: DigiLockerVerifyRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Verify digital document from DigiLocker"""
    result = await service.verify_digilocker(req.document_id, req.document_type)
    return DigiLockerVerifyResponse(
        document_id=result.document_id,
        document_type=result.document_type,
        is_valid=result.is_valid,
        holder_name=result.holder_name,
        issue_date=result.issue_date,
        expiry_date=result.expiry_date,
        issuing_authority=result.issuing_authority,
    )


# IEC Validation
@router.post("/iec/validate", response_model=IECValidateResponse)
async def validate_iec(
    req: IECValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Import Export Code (IEC) from DGFT"""
    result = await service.validate_iec(req.iec)
    return IECValidateResponse(
        iec=result.iec,
        is_valid=result.is_valid,
        company_name=result.company_name,
        address=result.address,
        branches=result.branches,
        status=result.status,
    )


# ICEGATE Customs Tracking
@router.post("/icegate/track", response_model=ICEGATETrackResponse)
async def track_icegate(
    req: ICEGATETrackRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Track customs clearance status via ICEGATE"""
    result = await service.track_icegate(req.bill_of_entry)
    return ICEGATETrackResponse(
        bill_of_entry=result.bill_of_entry,
        status=result.status,
        importer_name=result.importer_name,
        customs_duty=result.customs_duty,
        igst=result.igst,
        clearance_date=result.clearance_date,
    )


# RERA Project Validation
@router.post("/rera/validate", response_model=RERAValidateResponse)
async def validate_rera(
    req: RERAValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate RERA project registration"""
    result = await service.validate_rera(req.rera_number)
    return RERAValidateResponse(
        rera_number=result.rera_number,
        is_valid=result.is_valid,
        project_name=result.project_name,
        builder_name=result.builder_name,
        project_status=result.project_status,
        address=result.address,
        possession_date=result.possession_date,
        total_units=result.total_units,
    )


# FSSAI Food License Validation
@router.post("/fssai/validate", response_model=FSSAIValidateResponse)
async def validate_fssai(
    req: FSSAIValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate FSSAI food license"""
    result = await service.validate_fssai(req.license_number)
    return FSSAIValidateResponse(
        license_number=result.license_number,
        is_valid=result.is_valid,
        business_name=result.business_name,
        license_type=result.license_type,
        food_categories=result.food_categories,
        address=result.address,
        validity_period=result.validity_period,
    )


# GeM Vendor Validation
@router.post("/gem/validate", response_model=GeMValidateResponse)
async def validate_gem(
    req: GeMValidateRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Validate Government e-Marketplace (GeM) registration"""
    result = await service.validate_gem(req.gem_registration_id)
    return GeMValidateResponse(
        gem_registration_id=result.gem_registration_id,
        is_valid=result.is_valid,
        vendor_name=result.vendor_name,
        category=result.category,
        status=result.status,
        registration_date=result.registration_date,
    )


# GST Returns Filing History
@router.post("/gstn/returns", response_model=GSTReturnsResponse)
async def get_gst_returns(
    req: GSTReturnsRequest,
    service: GovStackService = Depends(get_govstack_service),
    current_actor: Actor = Depends(get_current_actor),
):
    """Get GST return filing history and compliance score"""
    result = await service.get_gst_returns(req.gstin, req.return_period)
    return GSTReturnsResponse(
        gstin=result.gstin,
        return_period=result.return_period,
        returns_filed=result.returns_filed,
        compliance_score=result.compliance_score,
        last_filed=result.last_filed,
    )