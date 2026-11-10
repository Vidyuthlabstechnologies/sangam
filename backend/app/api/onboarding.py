"""Onboarding, plans, prepaid wallet, tool connections and Play Store compliance endpoints.

Security model (this used to be wide open):
  * Every tenant-scoped route needs a logged-in actor AND ownership of the tenant
    (tenant_id == own actor id, or a wallet whose owner_actor_id is the caller).
    Unknown or foreign tenants answer 404 so ids cannot be probed.
  * Money only moves after Razorpay signature verification against a SERVER-priced
    order. No client-sent amount, plan price or phone number is ever trusted.
  * Call metering is webhook-only (see api/agent_callbacks.py), never a public route.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.config import settings
from app.core import composio_router, pricing
from app.core.account_deletion import purge_actor_personal_data
from app.core import legal_content
from app.core.billing_service import BillingError, BillingService
from app.core.onboarding_engine import (
    BUSINESS_TAXONOMY,
    SUPPORTED_INDIAN_LANGUAGES,
    SUPPORTED_MASCOTS,
    VERTICAL_PACKS,
    calculate_60_40_economics,
    generate_sim_forwarding_codes,
    generate_viral_marketing_kit,
    ingest_image_or_document_ocr,
    ingest_voice_or_text_narration,
    ingest_website_and_compile_agent,
)
from app.core.payments import RazorpayService
from app.core.sarvam import SarvamAI
from app.db.session import get_session
from app.models.actor import Actor
from app.models.sangamitra_release import (
    AccountDeletionAuditModel,
    AiSafetyReportModel,
    TenantAgentProfile,
    WalletOrderModel,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")


# --------------------------------------------------------------------- helpers
def _is_admin(actor: Actor) -> bool:
    return any(getattr(r, "value", r) == "admin" for r in (actor.roles or []))


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


async def resolve_tenant(
    session: AsyncSession, actor: Actor, tenant_id: Optional[str], *, create: bool = False
) -> str:
    """Return the tenant id the caller may act on, or raise. Foreign tenants look like missing ones."""
    own = str(actor.id)
    tid = (tenant_id or own).strip().lower()
    if tid == own:
        return tid
    if _looks_like_uuid(tid) or not _TENANT_RE.match(tid):
        raise HTTPException(status_code=404, detail="Business not found")
    wallet = await BillingService(session).get_wallet(tid)
    if wallet is None:
        if create:
            return tid
        raise HTTPException(status_code=404, detail="Business not found")
    if wallet.owner_actor_id == actor.id or _is_admin(actor):
        return tid
    raise HTTPException(status_code=404, detail="Business not found")


async def owned_tenant_ids(session: AsyncSession, actor: Actor) -> set[str]:
    """Tenant ids this actor may read. Admins are handled by the caller."""
    from app.models.sangamitra_release import TenantWalletModel

    ids = {str(actor.id)}
    rows = await session.execute(
        select(TenantWalletModel.tenant_id).where(TenantWalletModel.owner_actor_id == actor.id)
    )
    ids.update(rows.scalars().all())
    return ids


def _billing_http(exc: BillingError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


# -------------------------------------------------------------------- requests
class IngestUrlRequest(BaseModel):
    url: str = Field(..., max_length=500, description="Business website, Google Maps, or catalog link to ingest")
    languages: List[str] = Field(default=["kn-IN", "ml-IN", "te-IN"], max_length=22)
    mascot_id: Optional[str] = "v1"
    category_id: Optional[str] = None


class IngestVoiceNarrationRequest(BaseModel):
    narration: Optional[str] = Field(default=None, max_length=5000)
    transcript: Optional[str] = Field(default=None, max_length=5000)
    business_name_hint: Optional[str] = Field(default=None, max_length=200)
    primary_phone: Optional[str] = Field(default=None, max_length=20)
    language_code: Optional[str] = Field(default=None, max_length=16)
    languages: List[str] = Field(default=["kn-IN", "te-IN", "ml-IN", "hi-IN"], max_length=22)
    mascot_id: Optional[str] = "v1"


class IngestImageOcrRequest(BaseModel):
    extracted_text: str = Field(..., max_length=20000, description="OCR text from shop board, menu, brochure or card")
    filename: str = Field(default="shop_board.jpg", max_length=200)
    languages: List[str] = Field(default=["kn-IN", "hi-IN", "en-IN"], max_length=22)


class EconomicsRequest(BaseModel):
    upfront_inr: float = Field(default=2499.0, gt=0, le=1_000_000)
    raw_sarvam_per_min_inr: float = Field(default=3.0, gt=0, le=100)
    did_monthly_cost_inr: float = Field(default=59.0, ge=0, le=10_000)


class CreateOrderRequest(BaseModel):
    plan_id: Optional[str] = None
    topup_amount_inr: Optional[float] = Field(default=None, gt=0)
    tenant_id: Optional[str] = None
    business_name: Optional[str] = Field(default=None, max_length=200)
    mascot_id: Optional[str] = None
    primary_language: Optional[str] = Field(default=None, max_length=16)
    gstin: Optional[str] = Field(default=None, max_length=15)

    @model_validator(mode="after")
    def _one_purpose(self):
        if bool(self.plan_id) == bool(self.topup_amount_inr):
            raise ValueError("Send exactly one of plan_id or topup_amount_inr")
        return self


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(..., max_length=64)
    razorpay_payment_id: str = Field(..., max_length=64)
    razorpay_signature: str = Field(..., max_length=256)


class UpiAutopayRequest(BaseModel):
    tenant_id: Optional[str] = None
    enabled: bool = True
    threshold_inr: float = 30.0
    autopay_amount_inr: float = 299.0


class ApplyReferralRequest(BaseModel):
    tenant_id: Optional[str] = None
    referral_code: str = Field(..., max_length=40)


class ComposioConnectRequest(BaseModel):
    tenant_id: Optional[str] = None
    app_name: Optional[str] = None
    toolkit: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    target_config: Optional[Dict[str, Any]] = None


class ComposioExecuteRequest(BaseModel):
    tenant_id: Optional[str] = None
    caller_name: str = Field(..., max_length=200)
    caller_phone: str = Field(..., max_length=20)
    requirement_summary: str = Field(..., max_length=1000)
    language: str = "kn-IN"
    preferred_time: Optional[str] = Field(default=None, max_length=200)


class ReportAiOutputRequest(BaseModel):
    tenant_id: Optional[str] = None
    call_id: str = Field(..., max_length=64)
    utterance_flagged: Optional[str] = Field(default=None, max_length=2000)
    transcript_snippet: Optional[str] = Field(default=None, max_length=2000)
    reason: str = Field(default="inaccurate_or_inappropriate", max_length=120)


class SimForwardingBodyRequest(BaseModel):
    virtual_did: str = Field(default="+918064270314", max_length=20)
    carrier: str = "jio"


class SimulateTurnRequest(BaseModel):
    url: str = Field(default="https://abhishek-industries.pages.dev/", max_length=500)
    languages: List[str] = ["kn-IN", "ml-IN", "te-IN"]
    caller_language: str = "kn-IN"
    caller_utterance: str = Field(..., max_length=1000)
    synthesize_audio: bool = False


# ---------------------------------------------------------------- public routes
@router.get("/categories", response_model=Dict[str, Any])
async def list_onboarding_categories() -> Dict[str, Any]:
    """Pre-wired business categories, vertical packs, mascots, languages and plans. Public."""
    return {
        "supported_languages": SUPPORTED_INDIAN_LANGUAGES,
        "mascots": SUPPORTED_MASCOTS,
        "categories": BUSINESS_TAXONOMY,
        "vertical_packs": VERTICAL_PACKS,
        "plans": pricing.plan_catalog(),
        "default_economics": calculate_60_40_economics(),
    }


@router.get("/plans", response_model=Dict[str, Any])
async def list_plans() -> Dict[str, Any]:
    return {"gst_pct": pricing.GST_RATE_PCT, "plans": pricing.plan_catalog()}


@router.get("/vertical-packs", response_model=Dict[str, Any])
async def list_vertical_packs() -> Dict[str, Any]:
    return {"count": len(VERTICAL_PACKS), "vertical_packs": VERTICAL_PACKS}


@router.post("/calculate-economics", response_model=Dict[str, Any])
async def compute_economics(req: EconomicsRequest) -> Dict[str, Any]:
    return calculate_60_40_economics(
        upfront_inr=Decimal(str(req.upfront_inr)),
        raw_sarvam_per_min_inr=Decimal(str(req.raw_sarvam_per_min_inr)),
        did_monthly_cost_inr=Decimal(str(req.did_monthly_cost_inr)),
    )


@router.get("/sim-forwarding-codes", response_model=Dict[str, Any])
async def get_sim_forwarding_codes(
    virtual_number: str = Query(default="+918064270314", max_length=20),
) -> Dict[str, Any]:
    """Carrier-ready USSD call-forwarding codes for Jio, Airtel, Vi and BSNL."""
    return generate_sim_forwarding_codes(virtual_number=virtual_number)


@router.post("/sim-forwarding-codes", response_model=Dict[str, Any])
async def post_sim_forwarding_codes(req: SimForwardingBodyRequest) -> Dict[str, Any]:
    return generate_sim_forwarding_codes(virtual_number=req.virtual_did)


@router.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy_page() -> str:
    """Old URL kept for builds that still link to it; same page as /legal/privacy."""
    return legal_content.privacy_policy_html()


# ----------------------------------------------------- authenticated ingestion
@router.post("/ingest-url", response_model=Dict[str, Any])
async def ingest_business_url(req: IngestUrlRequest, actor: Actor = Depends(get_current_actor)) -> Dict[str, Any]:
    """Scrape a business URL (SSRF and brand-impersonation guarded) and compile a voice-agent spec."""
    try:
        spec = await ingest_website_and_compile_agent(url=req.url, languages=req.languages)
        data = asdict(spec)
        data["business_name"] = spec.business_profile.business_name
        return data
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read that URL. Check the link and try again.")


@router.post("/ingest-voice", response_model=Dict[str, Any])
async def ingest_spoken_narration(
    req: IngestVoiceNarrationRequest, actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    text = (req.narration or req.transcript or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Either narration or transcript is required")
    langs = [req.language_code] + req.languages if req.language_code else req.languages
    spec = ingest_voice_or_text_narration(
        narration=text,
        business_name_hint=req.business_name_hint,
        primary_phone=req.primary_phone,
        languages=langs,
    )
    data = asdict(spec)
    data["business_name"] = spec.business_profile.business_name
    return data


@router.post("/ingest-image", response_model=Dict[str, Any])
async def ingest_shop_board_or_brochure_ocr(
    req: IngestImageOcrRequest, actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    spec = ingest_image_or_document_ocr(
        extracted_text=req.extracted_text, filename=req.filename, languages=req.languages
    )
    return asdict(spec)


@router.post("/simulate-turn", response_model=Dict[str, Any])
async def simulate_multilingual_agent_turn(
    req: SimulateTurnRequest, actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    """Test a compiled agent on one caller line. Calls paid Sarvam APIs, so it needs a login."""
    try:
        spec = await ingest_website_and_compile_agent(url=req.url, languages=req.languages)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    sarvam = SarvamAI()
    messages = [
        {"role": "system", "content": spec.system_prompt + "\n\n" + spec.knowledge_base_markdown},
        {"role": "user", "content": req.caller_utterance},
    ]
    llm_resp = await sarvam.llm_complete(
        messages=messages, model="sarvam-105b-conversations", temperature=0.35, max_tokens=320
    )
    reply_text = llm_resp.content.strip()
    audio_b64: Optional[str] = None
    if req.synthesize_audio:
        tts_resp = await sarvam.text_to_speech(
            text=reply_text[:450], target_language_code=req.caller_language, speaker="priya"
        )
        audio_b64 = tts_resp.audio_base64
    return {
        "agent_name": spec.agent_name,
        "caller_language": req.caller_language,
        "caller_utterance": req.caller_utterance,
        "agent_reply": reply_text,
        "llm_model": llm_resp.model,
        "audio_synthesized": bool(audio_b64),
        "audio_base64_preview": (audio_b64[:80] + "...") if audio_b64 else None,
    }


# ------------------------------------------------------------- wallet and money
@router.get("/wallet/me", response_model=Dict[str, Any])
async def get_my_wallet(
    session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    svc = BillingService(session)
    wallet = await svc.get_or_create_wallet(str(actor.id), owner_actor_id=actor.id, business_name=actor.name)
    out = await svc.serialize(wallet)
    await session.commit()
    return out


@router.get("/wallet/{tenant_id}", response_model=Dict[str, Any])
async def get_tenant_wallet(
    tenant_id: str, session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, tenant_id)
    svc = BillingService(session)
    wallet = await svc.get_or_create_wallet(tid, owner_actor_id=actor.id if tid == str(actor.id) else None)
    out = await svc.serialize(wallet)
    await session.commit()
    return out


@router.post("/wallet/create-order", response_model=Dict[str, Any])
async def create_payment_order(
    req: CreateOrderRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    """Create a Razorpay order priced by the SERVER. The app opens Razorpay Checkout with the returned order id."""
    tid = await resolve_tenant(session, actor, req.tenant_id, create=True)
    if req.plan_id:
        plan = pricing.get_plan(req.plan_id)
        if plan is None:
            raise HTTPException(status_code=422, detail="Unknown plan")
        split = pricing.split_plan(plan)
        purpose = f"PLAN:{plan.plan_id}"
    else:
        if req.topup_amount_inr is None:
            raise HTTPException(status_code=422, detail="Send exactly one of plan_id or topup_amount_inr")
        base = int(round(req.topup_amount_inr * 100))
        if not (pricing.MIN_TOPUP_PAISE <= base <= pricing.MAX_TOPUP_PAISE):
            raise HTTPException(
                status_code=422,
                detail=f"Top-up must be between Rs. {pricing.MIN_TOPUP_PAISE // 100} and Rs. {pricing.MAX_TOPUP_PAISE // 100}",
            )
        split = pricing.split_topup(base)
        purpose = "TOPUP"

    svc = BillingService(session)
    wallet = await svc.get_or_create_wallet(
        tid,
        owner_actor_id=actor.id,
        business_name=req.business_name,
        mascot_id=req.mascot_id,
        primary_language=req.primary_language,
        gstin=req.gstin,
        lock=True,
    )
    if purpose == "TOPUP" and wallet.deployment_status == "UNPROVISIONED":
        raise HTTPException(status_code=409, detail="Buy a plan first, then you can top up")
    # Keep the business profile draft on the wallet so the plan payment can finish activation.
    if req.business_name:
        wallet.business_name = req.business_name
    if req.mascot_id in ("v1", "v2", "v3"):
        wallet.mascot_id = req.mascot_id
    if req.primary_language:
        wallet.primary_language = req.primary_language
    if req.gstin:
        wallet.gstin = req.gstin.strip().upper()

    receipt = f"sg_{uuid.uuid4().hex[:24]}"
    order = await RazorpayService().create_order(
        amount=split.total_paise / 100,
        receipt=receipt,
        notes={"tenant_id": tid, "purpose": purpose},
    )
    session.add(
        WalletOrderModel(
            razorpay_order_id=order["id"],
            tenant_id=tid,
            actor_id=actor.id,
            purpose=purpose,
            base_paise=split.base_paise,
            total_paise=split.total_paise,
        )
    )
    await session.commit()
    return {
        "order_id": order["id"],
        "key_id": settings.razorpay_key_id,
        "currency": "INR",
        "tenant_id": tid,
        "purpose": purpose,
        "price_inr": split.base_paise / 100,
        "gst_inr": split.gst_paise / 100,
        "amount_payable_inr": split.total_paise / 100,
        "amount_paise": split.total_paise,
        "included_minutes": split.included_minutes,
        "wallet_credit_inr": split.wallet_credit_paise / 100,
    }


@router.post("/wallet/verify-payment", response_model=Dict[str, Any])
async def verify_payment_and_credit(
    req: VerifyPaymentRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    """Verify the Razorpay signature for one of the caller's own orders, then credit the wallet exactly once."""
    order = (
        await session.execute(
            select(WalletOrderModel)
            .where(WalletOrderModel.razorpay_order_id == req.razorpay_order_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if order is None or order.actor_id != actor.id:
        raise HTTPException(status_code=404, detail="Order not found")

    rzp = RazorpayService()
    if not await rzp.verify_payment(req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment signature verification failed")

    if not rzp.use_fixtures:
        # Belt and braces: confirm with Razorpay that the money really is the amount we priced.
        details = await rzp.get_payment_details(req.razorpay_payment_id)
        if details.get("order_id") != order.razorpay_order_id or int(details.get("amount", -1)) != order.total_paise:
            raise HTTPException(status_code=400, detail="Payment does not match the order")
        if details.get("status") not in ("captured", "authorized"):
            raise HTTPException(status_code=400, detail="Payment not completed")

    svc = BillingService(session)
    try:
        if order.purpose.startswith("PLAN:"):
            plan = pricing.get_plan(order.purpose.split(":", 1)[1])
            if plan is None:
                raise HTTPException(status_code=409, detail="Plan no longer exists")
            result = await svc.credit_plan(
                order.tenant_id, plan, req.razorpay_payment_id, owner_actor_id=actor.id
            )
        else:
            result = await svc.credit_topup(order.tenant_id, order.base_paise, req.razorpay_payment_id)
    except BillingError as exc:
        raise _billing_http(exc)

    order.status = "PAID"
    order.razorpay_payment_id = req.razorpay_payment_id
    await session.commit()
    return result


@router.post("/wallet/autopay", response_model=Dict[str, Any])
async def configure_autopay(
    req: UpiAutopayRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    """Saves the auto-recharge preference. A real UPI mandate is not connected yet, so nothing is charged."""
    tid = await resolve_tenant(session, actor, req.tenant_id)
    try:
        out = await BillingService(session).configure_autopay(
            tid, req.enabled, req.threshold_inr, req.autopay_amount_inr
        )
    except BillingError as exc:
        raise _billing_http(exc)
    await session.commit()
    return out


@router.post("/wallet/referral", response_model=Dict[str, Any])
async def claim_referral_bonus(
    req: ApplyReferralRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, req.tenant_id)
    try:
        out = await BillingService(session).apply_referral(tid, req.referral_code)
    except BillingError as exc:
        raise _billing_http(exc)
    await session.commit()
    return out


@router.get("/gst-invoice/{tenant_id}", response_model=Dict[str, Any])
async def get_gst_invoice(
    tenant_id: str, session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    """Every GST tax invoice for the business, newest first. SAC 998315."""
    tid = await resolve_tenant(session, actor, tenant_id)
    try:
        invoices = await BillingService(session).invoices(tid)
    except BillingError as exc:
        raise _billing_http(exc)
    return {"tenant_id": tid, "count": len(invoices), "invoices": list(reversed(invoices))}


@router.get("/admin/economics", response_model=Dict[str, Any])
async def get_founder_economics_dashboard(
    session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Admin only")
    return await BillingService(session).platform_summary()


# --------------------------------------------------------------- tool connections
@router.get("/composio/tools", response_model=Dict[str, Any])
async def get_composio_tools_query(
    user_id: Optional[str] = Query(default=None, max_length=64),
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, user_id)
    return await composio_router.list_catalog_and_connections(session, tid)


@router.get("/composio/{tenant_id}", response_model=Dict[str, Any])
async def get_composio_tools(
    tenant_id: str, session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, tenant_id)
    return await composio_router.list_catalog_and_connections(session, tid)


@router.post("/composio/connect", response_model=Dict[str, Any])
async def connect_composio_tool(
    req: ComposioConnectRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    """Records a tool connection. SIMULATED until a real Composio account is configured."""
    tid = await resolve_tenant(session, actor, req.tenant_id, create=True)
    app_key = req.app_name or req.toolkit or "WHATSAPP"
    try:
        out = await composio_router.connect_tool(session, tid, app_key, req.metadata or req.target_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await session.commit()
    return out


@router.delete("/composio/connect/{tenant_id}/{app_name}", response_model=Dict[str, Any])
async def disconnect_composio_tool(
    tenant_id: str,
    app_name: str,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, tenant_id)
    out = await composio_router.disconnect_tool(session, tid, app_name)
    await session.commit()
    return out


@router.post("/composio/execute", response_model=Dict[str, Any])
async def execute_composio_post_call(
    req: ComposioExecuteRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, req.tenant_id)
    runs = await composio_router.execute_post_call_chain(
        session,
        tenant_id=tid,
        caller_name=req.caller_name,
        caller_phone=req.caller_phone,
        requirement_summary=req.requirement_summary,
        language=req.language,
        preferred_time=req.preferred_time,
    )
    await session.commit()
    return {"tenant_id": tid, "live": composio_router.LIVE, "executed_count": len(runs), "executions": runs}


@router.get("/viral-kit/{tenant_id}", response_model=Dict[str, Any])
async def get_tenant_viral_marketing_kit(
    tenant_id: str, session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    tid = await resolve_tenant(session, actor, tenant_id)
    wallet = await BillingService(session).get_or_create_wallet(tid, owner_actor_id=actor.id if tid == str(actor.id) else None)
    await session.commit()
    return generate_viral_marketing_kit(
        tenant_id=tid,
        business_name=wallet.business_name,
        assigned_did=wallet.assigned_did or "your Sangamitra number",
        mascot_id=wallet.mascot_id,
        referral_code=wallet.referral_code,
    )


# -------------------------------------------------------------------- compliance
@router.post("/report-ai-output", status_code=201, response_model=Dict[str, Any])
@router.post("/compliance/report-ai-output", status_code=201, response_model=Dict[str, Any])
async def report_ai_output(
    req: ReportAiOutputRequest,
    session: AsyncSession = Depends(get_session),
    actor: Actor = Depends(get_current_actor),
) -> Dict[str, Any]:
    """Google Play Generative AI policy: let users flag an inaccurate or offensive AI response."""
    tid = await resolve_tenant(session, actor, req.tenant_id)
    row = AiSafetyReportModel(
        report_id=f"rep_{uuid.uuid4().hex[:12]}",
        tenant_id=tid,
        call_id=req.call_id,
        utterance_flagged=req.utterance_flagged or req.transcript_snippet or "Flagged via Android app",
        reason=req.reason,
    )
    session.add(row)
    await session.commit()
    return {
        "report_id": row.report_id,
        "tenant_id": tid,
        "call_id": row.call_id,
        "reason": row.reason,
        "status": row.status,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/delete-account/{tenant_id}", response_model=Dict[str, Any])
@router.delete("/compliance/account/{tenant_id}", response_model=Dict[str, Any])
async def delete_tenant_account_and_data(
    tenant_id: str, session: AsyncSession = Depends(get_session), actor: Actor = Depends(get_current_actor)
) -> Dict[str, Any]:
    """Play Store account and data deletion (DPDP Act 2023). GST ledger rows are retained, anonymised."""
    tid = await resolve_tenant(session, actor, tenant_id)
    deleted = await BillingService(session).delete_tenant(tid)
    deleted.extend(await purge_actor_personal_data(session, actor, tid))
    profile = (
        await session.execute(select(TenantAgentProfile).where(TenantAgentProfile.tenant_id == tid))
    ).scalar_one_or_none()
    if profile is not None:
        await session.delete(profile)
        deleted.append("agent_profile")
    session.add(AccountDeletionAuditModel(tenant_id=tid, status="DELETED", deleted_items_json=deleted))
    await session.commit()
    return {
        "tenant_id": tid,
        "status": "DELETED",
        "deleted_items": deleted,
        "retained": ["gst_ledger_entries_anonymised"],
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }
