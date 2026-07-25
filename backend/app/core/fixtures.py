"""Deterministic canned responses for external services.

Active when a service's credentials are absent, or when settings.use_fixtures
is True. The same code paths run in both modes — only the transport is
swapped — so enabling live credentials is a config change, never a code
change.

Why this exists:
  * Tests stay hermetic: no network, no spend, no flakiness.
  * The demo runs end to end without live credentials.
  * Razorpay in particular must never be exercised with live keys during
    development, since escrow release is automatic and a logic bug would
    move real money.

The payloads below mirror the shape of real API responses. The CDSCO
licence is synthetic but realistic — a genuine Form 25 layout with a
plausible Karnataka manufacturing licence number.
"""
from __future__ import annotations

import base64
from typing import Any, Dict

# --------------------------------------------------------------------------
# Sarvam — document digitisation
# --------------------------------------------------------------------------

CDSCO_LICENCE_MARKDOWN = """# FORM 25
## LICENCE TO MANUFACTURE FOR SALE OR FOR DISTRIBUTION OF DRUGS
### (Other than those specified in Schedules C, C(1) and X)

**Licence Number:** MFG/25/2024/KA/00847

**Issued to:** Meridian Life Sciences Private Limited

**Premises:** Plot 14, Industrial Area Phase II, Peenya,
Bengaluru 560058, Karnataka

**Issuing Authority:** Drugs Control Department, Government of Karnataka

**Date of Issue:** 14/03/2024
**Valid Until:** 13/03/2029

**Categories of drugs authorised:**
1. Tablets (uncoated, film coated)
2. Capsules (hard gelatin)
3. Oral Liquids

**Competent Technical Staff:** Dr. S. Ramachandran, M.Pharm

**Conditions:** This licence is subject to the conditions prescribed under
the Drugs and Cosmetics Act 1940 and the Rules thereunder.
"""

EXTRACTED_LICENCE_JSON: Dict[str, Any] = {
    "licence_number": "MFG/25/2024/KA/00847",
    "vendor_name": "Meridian Life Sciences Private Limited",
    "address": "Plot 14, Industrial Area Phase II, Peenya, Bengaluru 560058, Karnataka",
    "issuing_authority": "Drugs Control Department, Government of Karnataka",
    "issue_date": "2024-03-14",
    "expiry_date": "2029-03-13",
    "licence_type": "CDSCO",
    "categories": ["Tablets", "Capsules", "Oral Liquids"],
    "confidence": {
        "licence_number": 0.97,
        "vendor_name": 0.95,
        "address": 0.88,
        "issuing_authority": 0.93,
        "issue_date": 0.96,
        "expiry_date": 0.96,
    },
}

# 0.1s of silence, 16 kHz mono PCM WAV. Real playable audio so the phone
# exercises its actual decode/playback path rather than a stub.
_SILENT_WAV = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00"
    b"data\x00\x00\x00\x00"
)

# A Hindi approval utterance — the vernacular path is the point of the
# Sarvam integration, so the fixture exercises non-Latin script end to end.
HINDI_APPROVAL_TRANSCRIPT = "मैं इस विक्रेता को मंजूरी देता हूं"


def sarvam_vision_job() -> Dict[str, Any]:
    return {
        "job_id": "fixture-job-0001",
        "storage_container": {"upload_url": ""},
    }


def sarvam_vision_status(job_id: str) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "status": "completed",
        "output": CDSCO_LICENCE_MARKDOWN,
    }


def sarvam_stt(language_code: str = "hi-IN") -> Dict[str, Any]:
    return {
        "transcript": HINDI_APPROVAL_TRANSCRIPT,
        "language_code": "hi-IN" if language_code in ("unknown", "hi-IN") else language_code,
        "language_probability": 0.94,
    }


def sarvam_tts() -> Dict[str, Any]:
    return {
        "audios": [base64.b64encode(_SILENT_WAV).decode()],
        "request_id": "fixture-tts-0001",
    }


def sarvam_llm(content: str) -> Dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def sarvam_translate(text: str) -> Dict[str, Any]:
    return {"translated_text": "I approve this vendor", "source_language_code": "hi-IN"}


# --------------------------------------------------------------------------
# Razorpay
# --------------------------------------------------------------------------

def razorpay_order(amount_paise: int, receipt: str, upi: bool = False) -> Dict[str, Any]:
    order: Dict[str, Any] = {
        "id": "order_FIXTURE00001",
        "entity": "order",
        "amount": amount_paise,
        "amount_paid": 0,
        "amount_due": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "status": "created",
        "attempts": 0,
    }
    if upi:
        # Mirrors the live API: method is a string; the intent flow is a
        # checkout-time concern recorded in notes.
        order["method"] = "upi"
        order["notes"] = {"upi_flow": "intent"}
    return order


def razorpay_payment(payment_id: str = "pay_FIXTURE00001") -> Dict[str, Any]:
    return {
        "id": payment_id,
        "entity": "payment",
        "status": "captured",
        "method": "upi",
        "currency": "INR",
        "vpa": "meridian@okhdfcbank",
    }


def razorpay_refund(payment_id: str) -> Dict[str, Any]:
    return {
        "id": "rfnd_FIXTURE00001",
        "entity": "refund",
        "payment_id": payment_id,
        "status": "processed",
    }
