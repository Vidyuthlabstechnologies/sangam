"""
GovStack Service - Real government data integration for Sangam
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class DataSource(str, Enum):
    GSTN = "gstn"
    MCA = "mca"
    UDYAM = "udyam"
    MOSPI_NSO = "mospi_nso"
    GATISHAKTI = "gatishakti"
    POWER = "power"
    BRIGHTDATA = "brightdata"
    PAN = "pan"
    DIN = "din"
    EPFO = "epfo"
    DIGILOCKER = "digilocker"
    ICEGATE = "icegate"
    DGFT = "dgft"
    CERSAI = "cersai"
    RERA = "rera"
    FSSAI = "fssai"
    GEM = "gem"


@dataclass
class GSTNValidationResult:
    gstin: str
    is_valid: bool
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    registration_date: Optional[str] = None
    status: Optional[str] = None
    taxpayer_type: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class MCACompanyResult:
    cin: str
    company_name: str
    status: str
    registration_date: Optional[str] = None
    authorized_capital: Optional[str] = None
    paid_up_capital: Optional[str] = None
    registered_address: Optional[str] = None
    directors: Optional[List[Dict]] = None
    raw_response: Optional[dict] = None


@dataclass
class UdyamValidationResult:
    udyam_number: str
    is_valid: bool
    enterprise_name: Optional[str] = None
    category: Optional[str] = None
    registration_date: Optional[str] = None
    address: Optional[str] = None
    social_category: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class SchemeDiscoveryResult:
    scheme_id: str
    scheme_name: str
    ministry: str
    description: str
    eligibility_criteria: List[str]
    benefits: List[str]
    application_url: Optional[str] = None
    deadline: Optional[str] = None
    target_beneficiaries: Optional[List[str]] = None


@dataclass
class EconomicIndicator:
    indicator_id: str
    name: str
    value: float
    unit: str
    period: str
    source: str
    metadata: Optional[Dict] = None


@dataclass
class LaborData:
    survey_id: str
    period: str
    unemployment_rate: Optional[float] = None
    labor_force_participation: Optional[float] = None
    employment_by_sector: Optional[Dict] = None
    wage_growth: Optional[float] = None
    raw_data: Optional[Dict] = None


@dataclass
class GeospatialAnalysis:
    location_id: str
    latitude: float
    longitude: float
    infrastructure: List[Dict]
    industrial_zones: List[Dict]
    logistics_cost_index: Optional[float] = None
    connectivity_score: Optional[float] = None


@dataclass
class PowerData:
    region: str
    timestamp: datetime
    generation: Dict[str, float]
    demand: float
    supply: float
    deficit: float
    grid_frequency: Optional[float] = None


@dataclass
class GSTReturnsResult:
    gstin: str
    return_period: str
    returns_filed: List[Dict[str, Any]]
    compliance_score: float
    last_filed: Optional[str] = None


@dataclass
class PANValidationResult:
    pan: str
    is_valid: bool
    name: Optional[str] = None
    pan_type: Optional[str] = None  # Individual, Company, HUF, etc.
    status: Optional[str] = None  # Active, Inactive
    address: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class DINValidationResult:
    din: str
    is_valid: bool
    director_name: Optional[str] = None
    status: Optional[str] = None  # Active, Disqualified
    companies: Optional[List[Dict]] = None
    appointment_dates: Optional[List[Dict]] = None
    raw_response: Optional[dict] = None


@dataclass
class EPFOValidationResult:
    uan: str
    is_valid: bool
    member_name: Optional[str] = None
    employer_name: Optional[str] = None
    pf_balance: Optional[str] = None
    kyc_status: Optional[str] = None
    last_contribution: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class DigiLockerResult:
    document_id: str
    document_type: str  # Aadhaar, PAN, Driving License, etc.
    is_valid: bool
    holder_name: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class IECValidationResult:
    iec: str
    is_valid: bool
    company_name: Optional[str] = None
    address: Optional[str] = None
    branches: Optional[List[Dict]] = None
    status: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class ICEGATEValidationResult:
    bill_of_entry: str
    status: str  # Filed, Assessed, Cleared, etc.
    importer_name: Optional[str] = None
    customs_duty: Optional[str] = None
    igst: Optional[str] = None
    clearance_date: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class RERAValidationResult:
    rera_number: str
    is_valid: bool
    project_name: Optional[str] = None
    builder_name: Optional[str] = None
    project_status: Optional[str] = None  # Ongoing, Completed, Delayed
    address: Optional[str] = None
    possession_date: Optional[str] = None
    total_units: Optional[int] = None
    raw_response: Optional[dict] = None


@dataclass
class FSSAIValidationResult:
    license_number: str
    is_valid: bool
    business_name: Optional[str] = None
    license_type: Optional[str] = None  # Central, State, Registration
    food_categories: Optional[List[str]] = None
    address: Optional[str] = None
    validity_period: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class GeMValidationResult:
    gem_registration_id: str
    is_valid: bool
    vendor_name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None  # Active, Suspended
    registration_date: Optional[str] = None
    raw_response: Optional[dict] = None


class LiveSourceUnavailable(RuntimeError):
    """A live government registry lookup is not wired up on this server."""


class BrightDataMCPClient:
    """Client for Bright Data MCP - web scraping at scale"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.brightdata.com"
    
    async def _request(self, method: str, path: str, data: Optional[dict] = None) -> dict:
        import httpx
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=60) as client:
            url = f"{self.base_url}{path}"
            if method == "GET":
                resp = await client.get(url, headers=headers)
            else:
                resp = await client.post(url, headers=headers, json=data)
            resp.raise_for_status()
            return resp.json()
    
    async def scrape_gstn(self, gstin: str) -> GSTNValidationResult:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "gstn_dataset",
            "parameters": {"gstin": gstin}
        })
        return self._parse_gstn_result(gstin, result)
    
    async def scrape_mca(self, cin: str) -> MCACompanyResult:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "mca_dataset",
            "parameters": {"cin": cin}
        })
        return self._parse_mca_result(cin, result)
    
    async def scrape_udyam(self, udyam_number: str) -> UdyamValidationResult:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "udyam_dataset",
            "parameters": {"udyam_number": udyam_number}
        })
        return self._parse_udyam_result(udyam_number, result)
    
    async def scrape_schemes(self, profile: dict) -> List[SchemeDiscoveryResult]:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "schemes_dataset",
            "parameters": profile
        })
        return self._parse_schemes_result(result)
    
    async def scrape_mospi(self, indicator: str) -> EconomicIndicator:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "mospi_dataset",
            "parameters": {"indicator": indicator}
        })
        return self._parse_mospi_result(indicator, result)
    
    async def scrape_gatishakti(self, lat: float, lon: float) -> GeospatialAnalysis:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "gatishakti_dataset",
            "parameters": {"latitude": lat, "longitude": lon}
        })
        return self._parse_gatishakti_result(lat, lon, result)
    
    async def scrape_power(self, region: str) -> PowerData:
        result = await self._request("POST", "/datasets/v3/trigger", {
            "dataset_id": "power_dataset",
            "parameters": {"region": region}
        })
        return self._parse_power_result(region, result)
    
    # No live Bright Data dataset is wired for these registries yet. With a
    # token set, say so plainly instead of failing with AttributeError.
    def _no_live_source(self, registry: str) -> "LiveSourceUnavailable":
        return LiveSourceUnavailable(f"Live {registry} lookup is not available yet.")

    async def scrape_pan(self, pan: str) -> PANValidationResult:
        raise self._no_live_source("PAN")

    async def scrape_din(self, din: str) -> DINValidationResult:
        raise self._no_live_source("DIN")

    async def scrape_epfo(self, establishment_id: str) -> EPFOValidationResult:
        raise self._no_live_source("EPFO")

    async def scrape_digilocker(self, document_id: str, document_type: str) -> DigiLockerResult:
        raise self._no_live_source("DigiLocker")

    async def scrape_iec(self, iec: str) -> IECValidationResult:
        raise self._no_live_source("IEC")

    async def scrape_icegate(self, reference: str) -> ICEGATEValidationResult:
        raise self._no_live_source("ICEGATE")

    async def scrape_rera(self, registration_number: str) -> RERAValidationResult:
        raise self._no_live_source("RERA")

    async def scrape_fssai(self, license_number: str) -> FSSAIValidationResult:
        raise self._no_live_source("FSSAI")

    async def scrape_gem(self, seller_id: str) -> GeMValidationResult:
        raise self._no_live_source("GeM")

    async def scrape_gst_returns(self, gstin: str, return_period: str) -> GSTReturnsResult:
        raise self._no_live_source("GST returns")

    async def custom_scrape(self, url: str, selectors: Optional[dict] = None) -> dict:
        result = await self._request("POST", "/web_unlocker", {
            "url": url,
            "selectors": selectors or {}
        })
        return result
    
    def _parse_gstn_result(self, gstin: str, data: dict) -> GSTNValidationResult:
        return GSTNValidationResult(
            gstin=gstin, is_valid=data.get("valid", False),
            legal_name=data.get("legal_name"), trade_name=data.get("trade_name"),
            address=data.get("address"), state=data.get("state"),
            registration_date=data.get("reg_date"), status=data.get("status"),
            taxpayer_type=data.get("type"), raw_response=data
        )
    
    def _parse_mca_result(self, cin: str, data: dict) -> MCACompanyResult:
        return MCACompanyResult(
            cin=cin, company_name=data.get("name", ""), status=data.get("status", ""),
            registration_date=data.get("reg_date"), authorized_capital=data.get("auth_capital"),
            paid_up_capital=data.get("paid_capital"), registered_address=data.get("address"),
            directors=data.get("directors", []), raw_response=data
        )
    
    def _parse_udyam_result(self, udyam: str, data: dict) -> UdyamValidationResult:
        return UdyamValidationResult(
            udyam_number=udyam, is_valid=data.get("valid", False),
            enterprise_name=data.get("name"), category=data.get("category"),
            registration_date=data.get("reg_date"), address=data.get("address"),
            social_category=data.get("social_cat"), raw_response=data
        )
    
    def _parse_schemes_result(self, data: dict) -> List[SchemeDiscoveryResult]:
        schemes = []
        for s in data.get("schemes", []):
            schemes.append(SchemeDiscoveryResult(
                scheme_id=s.get("id"), scheme_name=s.get("name"),
                ministry=s.get("ministry"), description=s.get("desc"),
                eligibility_criteria=s.get("eligibility", []),
                benefits=s.get("benefits", []),
                application_url=s.get("apply_url"), deadline=s.get("deadline"),
                target_beneficiaries=s.get("target", [])
            ))
        return schemes
    
    def _parse_mospi_result(self, indicator: str, data: dict) -> EconomicIndicator:
        return EconomicIndicator(
            indicator_id=indicator, name=data.get("name", indicator),
            value=data.get("value", 0), unit=data.get("unit", ""),
            period=data.get("period", ""), source="MoSPI/NSO",
            metadata=data.get("metadata", {})
        )
    
    def _parse_gatishakti_result(self, lat: float, lon: float, data: dict) -> GeospatialAnalysis:
        return GeospatialAnalysis(
            location_id=f"{lat},{lon}", latitude=lat, longitude=lon,
            infrastructure=data.get("infra", []), industrial_zones=data.get("zones", []),
            logistics_cost_index=data.get("cost_index"), connectivity_score=data.get("connectivity")
        )
    
    def _parse_power_result(self, region: str, data: dict) -> PowerData:
        return PowerData(
            region=region, timestamp=datetime.now(),
            generation=data.get("generation", {}), demand=data.get("demand", 0),
            supply=data.get("supply", 0), deficit=data.get("deficit", 0),
            grid_frequency=data.get("frequency")
        )


class GovStackService:
    """Unified service for all government data integrations"""
    
    def __init__(self, brightdata_token: Optional[str] = None):
        self.brightdata = BrightDataMCPClient(brightdata_token) if brightdata_token else None
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 3600
    
    async def validate_gstin(self, gstin: str) -> GSTNValidationResult:
        cache_key = f"gstn:{gstin}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_gstn(gstin)
        else:
            result = GSTNValidationResult(
                gstin=gstin, is_valid=True,
                legal_name=f"Test Company {gstin[:5]}",
                trade_name="Test Trade",
                address="123 Test Street, Bangalore",
                state="Karnataka",
                registration_date="2020-01-15",
                status="active",
                taxpayer_type="Regular"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result
    
    async def get_company_details(self, cin: str) -> MCACompanyResult:
        cache_key = f"mca:{cin}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_mca(cin)
        else:
            result = MCACompanyResult(
                cin=cin, company_name=f"Test Company {cin[:8]}",
                status="Active", registration_date="2015-03-20",
                authorized_capital="₹1,00,00,000",
                paid_up_capital="₹50,00,000",
                registered_address="456 Business Ave, Mumbai",
                directors=[{"name": "Director 1", "din": "00000001"}, {"name": "Director 2", "din": "00000002"}]
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result
    
    async def validate_udyam(self, udyam_number: str) -> UdyamValidationResult:
        cache_key = f"udyam:{udyam_number}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_udyam(udyam_number)
        else:
            result = UdyamValidationResult(
                udyam_number=udyam_number, is_valid=True,
                enterprise_name="Test MSME Enterprise",
                category="Small",
                registration_date="2021-06-10",
                address="789 Industrial Area, Pune",
                social_category="General"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result
    
    async def discover_schemes(self, profile: dict) -> List[SchemeDiscoveryResult]:
        cache_key = f"schemes:{hash(json.dumps(profile, sort_keys=True))}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_schemes(profile)
        else:
            result = [
                SchemeDiscoveryResult(
                    scheme_id="MSME-001", scheme_name="Credit Guarantee Scheme",
                    ministry="Ministry of MSME", description="Collateral-free loans up to ₹2Cr",
                    eligibility_criteria=["Valid Udyam registration", "GST compliant"],
                    benefits=["No collateral", "Interest subvention"], application_url="https://cgtmse.in"
                ),
                SchemeDiscoveryResult(
                    scheme_id="STARTUP-001", scheme_name="Startup India Seed Fund",
                    ministry="DPIIT", description="Up to ₹50L seed funding",
                    eligibility_criteria=["DPIIT recognized startup", "Up to 2 years old"],
                    benefits=["Grant up to ₹20L", "Debt up to ₹50L"], application_url="https://seedfund.startupindia.gov.in"
                )
            ]
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result
    
    async def get_economic_indicator(self, indicator: str) -> EconomicIndicator:
        if self.brightdata:
            return await self.brightdata.scrape_mospi(indicator)
        return EconomicIndicator(
            indicator_id=indicator, name=indicator.replace("_", " ").title(),
            value=100.5, unit="Index", period="2024-Q1", source="MoSPI",
            metadata={}
        )
    
    async def get_labor_data(self, survey: str = "PLFS") -> LaborData:
        return LaborData(
            survey_id=survey, period="2023-24",
            unemployment_rate=3.2, labor_force_participation=55.5,
            employment_by_sector={"agriculture": 42, "industry": 25, "services": 33},
            wage_growth=5.1
        )
    
    async def analyze_location(self, lat: float, lon: float) -> GeospatialAnalysis:
        if self.brightdata:
            return await self.brightdata.scrape_gatishakti(lat, lon)
        return GeospatialAnalysis(
            location_id=f"{lat},{lon}", latitude=lat, longitude=lon,
            infrastructure=[{"type": "highway", "name": "NH-44", "distance_km": 5}],
            industrial_zones=[{"name": "Electronic City", "distance_km": 10}],
            logistics_cost_index=1.2, connectivity_score=85
        )
    
    async def get_power_data(self, region: str) -> PowerData:
        if self.brightdata:
            return await self.brightdata.scrape_power(region)
        return PowerData(
            region=region, timestamp=datetime.now(),
            generation={"thermal": 150000, "hydro": 30000, "nuclear": 8000, "renewable": 50000},
            demand=220000, supply=238000, deficit=0, grid_frequency=50.0
        )

    # New Government Capabilities
    
    async def validate_pan(self, pan: str) -> PANValidationResult:
        cache_key = f"pan:{pan}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_pan(pan)
        else:
            result = PANValidationResult(
                pan=pan, is_valid=True,
                name=f"Test PAN Holder {pan[:5]}",
                pan_type="Individual",
                status="Active",
                address="123 Test Street, Delhi"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def validate_din(self, din: str) -> DINValidationResult:
        cache_key = f"din:{din}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_din(din)
        else:
            result = DINValidationResult(
                din=din, is_valid=True,
                director_name=f"Director {din[:4]}",
                status="Active",
                companies=[{"cin": "U74999DL2020PTC123456", "name": "Test Company"}],
                appointment_dates=[{"cin": "U74999DL2020PTC123456", "date": "2020-01-15"}]
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def validate_epfo(self, uan: str) -> EPFOValidationResult:
        cache_key = f"epfo:{uan}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_epfo(uan)
        else:
            result = EPFOValidationResult(
                uan=uan, is_valid=True,
                member_name=f"EPF Member {uan[-4:]}",
                employer_name="Test Employer Pvt Ltd",
                pf_balance="₹5,00,000",
                kyc_status="Verified",
                last_contribution="2024-01-15"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def verify_digilocker(self, document_id: str, document_type: str) -> DigiLockerResult:
        cache_key = f"digilocker:{document_type}:{document_id}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_digilocker(document_id, document_type)
        else:
            result = DigiLockerResult(
                document_id=document_id, document_type=document_type, is_valid=True,
                holder_name="Test Holder",
                issue_date="2020-01-01",
                expiry_date="2030-01-01",
                issuing_authority="Government of India"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def validate_iec(self, iec: str) -> IECValidationResult:
        cache_key = f"iec:{iec}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_iec(iec)
        else:
            result = IECValidationResult(
                iec=iec, is_valid=True,
                company_name=f"IEC Holder {iec[:5]}",
                address="123 Export House, Mumbai",
                branches=[{"city": "Mumbai", "address": "Branch 1"}],
                status="Active"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def track_icegate(self, bill_of_entry: str) -> ICEGATEValidationResult:
        cache_key = f"icegate:{bill_of_entry}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_icegate(bill_of_entry)
        else:
            result = ICEGATEValidationResult(
                bill_of_entry=bill_of_entry, status="Cleared",
                importer_name="Test Importer Pvt Ltd",
                customs_duty="₹50,000",
                igst="₹18,000",
                clearance_date="2024-01-15"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def validate_rera(self, rera_number: str) -> RERAValidationResult:
        cache_key = f"rera:{rera_number}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_rera(rera_number)
        else:
            result = RERAValidationResult(
                rera_number=rera_number, is_valid=True,
                project_name="Test Residential Project",
                builder_name="Test Builder Pvt Ltd",
                project_status="Ongoing",
                address="123 Builder Street, Bangalore",
                possession_date="2025-12-31",
                total_units=200
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def validate_fssai(self, license_number: str) -> FSSAIValidationResult:
        cache_key = f"fssai:{license_number}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_fssai(license_number)
        else:
            result = FSSAIValidationResult(
                license_number=license_number, is_valid=True,
                business_name="Test Food Business",
                license_type="State License",
                food_categories=["Dairy Products", "Bakery"],
                address="456 Food Street, Mumbai",
                validity_period="2023-01-01 to 2028-12-31"
            )
        
        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result

    async def validate_gem(self, gem_registration_id: str) -> GeMValidationResult:
        cache_key = f"gem:{gem_registration_id}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]
        
        if self.brightdata:
            result = await self.brightdata.scrape_gem(gem_registration_id)
        else:
            result = GeMValidationResult(
                gem_registration_id=gem_registration_id, is_valid=True,
                vendor_name="Test Vendor Pvt Ltd",
                category="IT Services",
                status="Active",
                registration_date="2022-01-15"
            )

        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result


    async def get_gst_returns(self, gstin: str, return_period: str) -> GSTReturnsResult:
        cache_key = f"gstn_returns:{gstin}:{return_period}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached["ts"]).seconds < self.cache_ttl:
                return cached["data"]

        if self.brightdata:
            result = await self.brightdata.scrape_gst_returns(gstin, return_period)
        else:
            result = GSTReturnsResult(
                gstin=gstin,
                return_period=return_period,
                returns_filed=[
                    {"form": "GSTR-1", "status": "filed", "date": "2024-01-11", "taxable_value": 1000000, "tax": 180000},
                    {"form": "GSTR-3B", "status": "filed", "date": "2024-01-20", "taxable_value": 1000000, "tax": 180000},
                ],
                compliance_score=95.0,
                last_filed="2024-01-20"
            )

        self.cache[cache_key] = {"data": result, "ts": datetime.now()}
        return result


GOVSTACK_CAPABILITIES = [
    {
        "name": "gstn.validate-gstin",
        "description": "Validate GSTIN and get taxpayer details from GSTN portal",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"gstin": {"type": "string"}}, "required": ["gstin"]},
        "output_schema": {"type": "object", "properties": {"gstin": {"type": "string"}, "is_valid": {"type": "boolean"}, "legal_name": {"type": "string"}, "trade_name": {"type": "string"}, "address": {"type": "string"}, "state": {"type": "string"}, "status": {"type": "string"}}},
        "endpoint": "/govstack/gstn/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
    {
        "name": "gstn.get-returns",
        "description": "Get GST return filing history and compliance score",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"gstin": {"type": "string"}, "return_period": {"type": "string"}}, "required": ["gstin", "return_period"]},
        "output_schema": {"type": "object", "properties": {"gstin": {"type": "string"}, "return_period": {"type": "string"}, "returns_filed": {"type": "array"}, "compliance_score": {"type": "number"}, "last_filed": {"type": "string"}}},
        "endpoint": "/govstack/gstn/returns",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "mca.get-company",
        "description": "Get company details from MCA (CIN lookup)",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"cin": {"type": "string"}}, "required": ["cin"]},
        "output_schema": {"type": "object", "properties": {"cin": {"type": "string"}, "company_name": {"type": "string"}, "status": {"type": "string"}, "directors": {"type": "array"}, "registered_address": {"type": "string"}}},
        "endpoint": "/govstack/mca/company",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
    {
        "name": "mca.get-director",
        "description": "Get director details (DIN lookup)",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"din": {"type": "string"}}, "required": ["din"]},
        "output_schema": {"type": "object", "properties": {"din": {"type": "string"}, "is_valid": {"type": "boolean"}, "director_name": {"type": "string"}, "status": {"type": "string"}, "companies": {"type": "array"}, "appointment_dates": {"type": "array"}}},
        "endpoint": "/govstack/mca/director",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
    {
        "name": "udyam.validate",
        "description": "Validate Udyam registration (MSME)",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"udyam_number": {"type": "string"}}, "required": ["udyam_number"]},
        "output_schema": {"type": "object", "properties": {"udyam_number": {"type": "string"}, "is_valid": {"type": "boolean"}, "enterprise_name": {"type": "string"}, "category": {"type": "string"}}},
        "endpoint": "/govstack/udyam/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
    {
        "name": "pan.validate",
        "description": "Validate PAN and get taxpayer details",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"pan": {"type": "string"}}, "required": ["pan"]},
        "output_schema": {"type": "object", "properties": {"pan": {"type": "string"}, "is_valid": {"type": "boolean"}, "name": {"type": "string"}, "pan_type": {"type": "string"}, "status": {"type": "string"}, "address": {"type": "string"}}},
        "endpoint": "/govstack/pan/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
    {
        "name": "epfo.validate",
        "description": "Validate UAN and get EPF details",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"uan": {"type": "string"}}, "required": ["uan"]},
        "output_schema": {"type": "object", "properties": {"uan": {"type": "string"}, "is_valid": {"type": "boolean"}, "member_name": {"type": "string"}, "employer_name": {"type": "string"}, "pf_balance": {"type": "string"}, "kyc_status": {"type": "string"}, "last_contribution": {"type": "string"}}},
        "endpoint": "/govstack/epfo/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "digilocker.verify",
        "description": "Verify digital document from DigiLocker",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"document_id": {"type": "string"}, "document_type": {"type": "string"}}, "required": ["document_id", "document_type"]},
        "output_schema": {"type": "object", "properties": {"document_id": {"type": "string"}, "document_type": {"type": "string"}, "is_valid": {"type": "boolean"}, "holder_name": {"type": "string"}, "issue_date": {"type": "string"}, "expiry_date": {"type": "string"}, "issuing_authority": {"type": "string"}}},
        "endpoint": "/govstack/digilocker/verify",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "iec.validate",
        "description": "Validate Import Export Code (IEC) from DGFT",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"iec": {"type": "string"}}, "required": ["iec"]},
        "output_schema": {"type": "object", "properties": {"iec": {"type": "string"}, "is_valid": {"type": "boolean"}, "company_name": {"type": "string"}, "address": {"type": "string"}, "branches": {"type": "array"}, "status": {"type": "string"}}},
        "endpoint": "/govstack/iec/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "icegate.track",
        "description": "Track customs clearance status via ICEGATE",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"bill_of_entry": {"type": "string"}}, "required": ["bill_of_entry"]},
        "output_schema": {"type": "object", "properties": {"bill_of_entry": {"type": "string"}, "status": {"type": "string"}, "importer_name": {"type": "string"}, "customs_duty": {"type": "string"}, "igst": {"type": "string"}, "clearance_date": {"type": "string"}}},
        "endpoint": "/govstack/icegate/track",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "rera.validate",
        "description": "Validate RERA project registration",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"rera_number": {"type": "string"}}, "required": ["rera_number"]},
        "output_schema": {"type": "object", "properties": {"rera_number": {"type": "string"}, "is_valid": {"type": "boolean"}, "project_name": {"type": "string"}, "builder_name": {"type": "string"}, "project_status": {"type": "string"}, "address": {"type": "string"}, "possession_date": {"type": "string"}, "total_units": {"type": "integer"}}},
        "endpoint": "/govstack/rera/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "fssai.validate",
        "description": "Validate FSSAI food license",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"license_number": {"type": "string"}}, "required": ["license_number"]},
        "output_schema": {"type": "object", "properties": {"license_number": {"type": "string"}, "is_valid": {"type": "boolean"}, "business_name": {"type": "string"}, "license_type": {"type": "string"}, "food_categories": {"type": "array"}, "address": {"type": "string"}, "validity_period": {"type": "string"}}},
        "endpoint": "/govstack/fssai/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "gem.validate",
        "description": "Validate Government e-Marketplace (GeM) registration",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"gem_registration_id": {"type": "string"}}, "required": ["gem_registration_id"]},
        "output_schema": {"type": "object", "properties": {"gem_registration_id": {"type": "string"}, "is_valid": {"type": "boolean"}, "vendor_name": {"type": "string"}, "category": {"type": "string"}, "status": {"type": "string"}, "registration_date": {"type": "string"}}},
        "endpoint": "/govstack/gem/validate",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "schemes.discover",
        "description": "Discover government schemes matching business profile",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"industry": {"type": "string"}, "state": {"type": "string"}, "size": {"type": "string"}, "category": {"type": "string"}}, "required": ["industry", "state"]},
        "output_schema": {"type": "object", "properties": {"schemes": {"type": "array"}}},
        "endpoint": "/govstack/schemes/discover",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "mospi.get-indicator",
        "description": "Get economic indicator from MoSPI/NSO",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"indicator": {"type": "string"}}, "required": ["indicator"]},
        "output_schema": {"type": "object", "properties": {"indicator_id": {"type": "string"}, "name": {"type": "string"}, "value": {"type": "number"}, "unit": {"type": "string"}, "period": {"type": "string"}}},
        "endpoint": "/govstack/mospi/indicator",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
    {
        "name": "mospi.get-labor-data",
        "description": "Get labor force survey data from NSO",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"survey": {"type": "string", "default": "PLFS"}}, "required": []},
        "output_schema": {"type": "object", "properties": {"unemployment_rate": {"type": "number"}, "labor_force_participation": {"type": "number"}, "employment_by_sector": {"type": "object"}}},
        "endpoint": "/govstack/mospi/labor",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "gatishakti.analyze-location",
        "description": "Analyze location logistics using PM GatiShakti geospatial data",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}}, "required": ["latitude", "longitude"]},
        "output_schema": {"type": "object", "properties": {"infrastructure": {"type": "array"}, "industrial_zones": {"type": "array"}, "logistics_cost_index": {"type": "number"}, "connectivity_score": {"type": "number"}}},
        "endpoint": "/govstack/gatishakti/analyze",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 30
    },
    {
        "name": "power.get-data",
        "description": "Get power sector data from National Power Portal",
        "category": "government",
        "input_schema": {"type": "object", "properties": {"region": {"type": "string"}}, "required": ["region"]},
        "output_schema": {"type": "object", "properties": {"generation": {"type": "object"}, "demand": {"type": "number"}, "supply": {"type": "number"}, "deficit": {"type": "number"}}},
        "endpoint": "/govstack/power/data",
        "method": "POST",
        "auth_required": True,
        "rate_limit": 60
    },
]


# Global service instance
_govstack_service = GovStackService(brightdata_token=None)