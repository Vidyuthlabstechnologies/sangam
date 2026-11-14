"""Bulk calling campaigns: who to dial next, how many at once, and when to stop.

There is no background worker. Cloud Run may freeze an idle instance, so the
campaign moves forward whenever something touches it:

  * starting or resuming it,
  * a call outcome arriving on the Samvaad webhook (a line just came free),
  * anyone viewing its progress (the app polls the live view every few seconds).

Each of those runs ``advance()``, which settles finished calls, then tops the
campaign back up to ``concurrency`` live calls until the goal is met or the
list runs out. ``advance()`` locks the campaign row, so two of them never dial
the same contact.

Indian calling rules this enforces (TRAI TCCCPR 2018):
  * Calls go out only inside the campaign's window, which must sit within
    09:00-21:00 IST.
  * A live campaign starts only after the owner confirms the list is scrubbed
    against the NCPR (DND) registry or has opted in.
  * Anyone who asks not to be called again goes on the business's do-not-call
    list, which every later upload and dial checks.

Simulation mode never dials: each call plays out on the server clock with a
scripted conversation in the contact's language, and spends nothing.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
import math
import random
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.billing_service import STATUS_PAUSED_ZERO, BillingService
from app.core.samvaad import SamvaadClient
from app.models.campaign import (
    CallCampaign,
    CampaignContact,
    CampaignStatus,
    ContactStatus,
    DoNotCallEntry,
)
from app.models.samvaad import (
    SamvaadAgentBinding,
    SamvaadCallAttempt,
    SamvaadCallStatus,
)
from app.models.sangamitra_release import utcnow_naive

logger = logging.getLogger("sangam.campaigns")

IST = timedelta(hours=5, minutes=30)
# TRAI: commercial calls only between 09:00 and 21:00.
LEGAL_START_HOUR = 9
LEGAL_END_HOUR = 21
MAX_CONTACTS = 5000
# New calls placed per advance(); keeps one request short. The next tick places more.
LIVE_DIALS_PER_TICK = 25
SIM_DIALS_PER_TICK = 500
# A live call with no outcome after this long is written off.
LIVE_CALL_TIMEOUT = timedelta(minutes=20)
# For the "versus a telecaller" comparison: what a person spends per dial
# beyond talk time (dialling, ringing out, writing notes).
HUMAN_OVERHEAD_SECONDS = 60
HUMAN_RING_SECONDS = 30

WebhookUrlFor = Callable[[str], str]


# ---------------------------------------------------------------------------
# Phone numbers and CSV
# ---------------------------------------------------------------------------

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone(raw: str) -> str | None:
    """Indian numbers in any common shape to E.164; other countries need a +."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    if s.startswith("+"):
        return s if _E164.match(s) else None
    if s.startswith("0") and len(s) == 11:
        s = s[1:]
    if len(s) == 12 and s.startswith("91"):
        s = s[2:]
    if len(s) == 10 and s[0] in "6789" and s.isdigit():
        return "+91" + s
    return None


def mask_phone(number: str) -> str:
    return number[:3] + "*" * max(len(number) - 7, 0) + number[-4:]


_LANG_ALIASES = {
    "en": "English", "eng": "English", "english": "English",
    "hi": "Hindi", "hin": "Hindi", "hindi": "Hindi",
    "te": "Telugu", "tel": "Telugu", "telugu": "Telugu",
    "ta": "Tamil", "tamil": "Tamil",
    "kn": "Kannada", "kannada": "Kannada",
    "ml": "Malayalam", "malayalam": "Malayalam",
    "mr": "Marathi", "marathi": "Marathi",
    "bn": "Bengali", "bengali": "Bengali",
    "gu": "Gujarati", "gujarati": "Gujarati",
    "pa": "Punjabi", "punjabi": "Punjabi",
    "or": "Odia", "od": "Odia", "odia": "Odia",
}


def normalize_language(raw: str | None) -> str | None:
    if not raw:
        return None
    return _LANG_ALIASES.get(raw.strip().lower())


_PHONE_COLS = ("phone", "mobile", "number", "phone_number", "mobile_number", "contact", "msisdn")
_NAME_COLS = ("name", "full_name", "customer", "customer_name", "first_name")
_LANG_COLS = ("language", "lang", "preferred_language")
_DND_COLS = ("dnd", "ncpr", "do_not_call")
_TRUTHY = {"1", "true", "yes", "y"}


def parse_contacts_csv(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rows -> ([{name, phone, language, variables, dnd}], [{line, reason}]).

    Needs a header row with a phone column (phone, mobile or number). A name and
    a language column are used when present; every other column is passed to
    the agent as a variable, so a script can mention "{plot_size}" and the like.
    A truthy "dnd" column marks the number as registered on the NCPR.
    """
    text = (text or "").lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=422, detail="The file is empty")
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]

    def col(options: tuple[str, ...]) -> int | None:
        for opt in options:
            if opt in header:
                return header.index(opt)
        return None

    phone_i = col(_PHONE_COLS)
    if phone_i is None:
        raise HTTPException(status_code=422, detail="Add a header row with a 'phone' column")
    name_i, lang_i, dnd_i = col(_NAME_COLS), col(_LANG_COLS), col(_DND_COLS)
    known = {i for i in (phone_i, name_i, lang_i, dnd_i) if i is not None}

    good: list[dict[str, Any]] = []
    bad: list[dict[str, Any]] = []
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        def cell(i: int | None, row: list[str] = row) -> str:
            return row[i].strip() if i is not None and i < len(row) else ""

        phone = normalize_phone(cell(phone_i))
        if phone is None:
            bad.append({"line": line_no, "reason": "phone number not recognised"})
            continue
        variables = {
            header[i]: row[i].strip()[:200]
            for i in range(min(len(header), len(row)))
            if i not in known and header[i] and row[i].strip()
        }
        good.append({
            "name": cell(name_i)[:120],
            "phone": phone,
            "language": normalize_language(cell(lang_i)),
            "variables": dict(list(variables.items())[:20]) or None,
            "dnd": cell(dnd_i).lower() in _TRUTHY,
        })
    return good, bad


# ---------------------------------------------------------------------------
# Calling hours
# ---------------------------------------------------------------------------

def now() -> datetime:
    """The engine's clock (naive UTC). One function, so tests can move time."""
    return utcnow_naive()


def ist_now(now_utc: datetime | None = None) -> datetime:
    return (now_utc or utcnow_naive()) + IST


def in_calling_window(campaign: CallCampaign, now_utc: datetime | None = None) -> bool:
    hour = ist_now(now_utc).hour
    start = max(campaign.window_start_hour, LEGAL_START_HOUR)
    end = min(campaign.window_end_hour, LEGAL_END_HOUR)
    return start <= hour < end


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in _TRUTHY | {"opted_out", "opt_out", "stop"}


def is_success(campaign: CallCampaign, final_vars: dict[str, Any] | None) -> bool:
    if not final_vars:
        return False
    value = final_vars.get(campaign.success_variable)
    if value is None:
        return False
    accepted = {v.strip().lower() for v in (campaign.success_values or [])} or _TRUTHY
    return str(value).strip().lower() in accepted


def summarize(status: str, final_vars: dict[str, Any] | None, transcript: list[dict[str, Any]] | None) -> str:
    final_vars = final_vars or {}
    for key in ("summary", "call_summary", "outcome_summary"):
        if final_vars.get(key):
            return str(final_vars[key])[:500]
    if status == ContactStatus.NO_ANSWER:
        return "Did not pick up."
    if status == ContactStatus.BUSY:
        return "Line was busy."
    if status == ContactStatus.FAILED:
        return "Call could not be completed."
    last_user = next((t.get("content") for t in reversed(transcript or []) if t.get("role") == "user"), None)
    return f"Spoke with the agent. Last said: \"{last_user}\""[:500] if last_user else "Spoke with the agent."


async def _add_dnc(session: AsyncSession, tenant_id: str, phone: str, reason: str) -> None:
    exists = await session.scalar(
        select(DoNotCallEntry.id).where(DoNotCallEntry.tenant_id == tenant_id, DoNotCallEntry.phone == phone)
    )
    if exists is None:
        session.add(DoNotCallEntry(tenant_id=tenant_id, phone=phone, reason=reason))


async def apply_outcome(
    session: AsyncSession,
    campaign: CallCampaign,
    contact: CampaignContact,
    *,
    status: str,
    duration: float | None,
    final_vars: dict[str, Any] | None,
    transcript: list[dict[str, Any]] | None,
    summary: str | None = None,
) -> None:
    """Record how one call went. Safe to call twice: a settled contact is left alone."""
    if contact.status != ContactStatus.DIALING:
        return
    status = status if status in ContactStatus.FINAL else ContactStatus.FAILED
    contact.duration_seconds = duration
    contact.transcript = transcript or None
    contact.completed_at = utcnow_naive()
    contact.summary = summary or summarize(status, final_vars, transcript)
    if status == ContactStatus.CONNECTED:
        contact.succeeded = is_success(campaign, final_vars)
        if final_vars and _truthy(final_vars.get("opt_out", "")):
            contact.opted_out = True
            await _add_dnc(session, campaign.tenant_id, contact.phone, "opted_out")
    if contact.succeeded:
        campaign.success_count += 1
    if (
        status in ContactStatus.RETRYABLE
        and contact.attempts < campaign.max_attempts
        and campaign.status not in CampaignStatus.FINISHED
    ):
        contact.status = ContactStatus.PENDING  # back in the queue, after fresh numbers
    else:
        contact.status = status


async def on_call_finished(
    session: AsyncSession, call: SamvaadCallAttempt, webhook_url_for: WebhookUrlFor
) -> None:
    """The Samvaad webhook settled a call; if it belonged to a campaign, record it and refill."""
    contact = (
        await session.execute(select(CampaignContact).where(CampaignContact.call_id == call.id))
    ).scalar_one_or_none()
    if contact is None:
        return
    campaign = await _lock_campaign(session, contact.campaign_id)
    if campaign is None:
        return
    await session.refresh(contact)
    await apply_outcome(
        session,
        campaign,
        contact,
        status=call.status,
        duration=call.duration_seconds,
        final_vars=call.final_agent_variables,
        transcript=call.transcript,
    )
    await session.commit()
    await advance(session, campaign.id, webhook_url_for)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

# Scripted calls, one set per language. {name}, {business} and {pitch} are filled in.
_SCRIPTS: dict[str, dict[str, Any]] = {
    "English": {
        "open": [
            ("agent", "Hello {name}, this is Priya calling from {business}. Do you have a minute?"),
            ("user", "Yes, go ahead."),
            ("agent", "Thank you! I'm calling about {pitch}. Would that interest you?"),
        ],
        "success": [
            ("user", "Actually yes. How much does it cost?"),
            ("agent", "It depends on what you choose. Our team will walk you through every option, with no obligation. Would Saturday at 11 AM suit you?"),
            ("user", "Saturday works. Book it."),
            ("agent", "Done! You're booked for Saturday at 11 AM. You'll get an SMS confirmation shortly. Thank you, {name}!"),
        ],
        "not_interested": [
            ("user", "Not right now, thanks."),
            ("agent", "No problem at all. If anything changes, just call us back. Have a good day!"),
        ],
        "callback": [
            ("user", "I'm a bit busy now. Can you call me in the evening?"),
            ("agent", "Of course. We'll call you back after 6 PM today. Thank you!"),
        ],
        "opt_out": [
            ("user", "Please don't call me again."),
            ("agent", "I'm sorry for the trouble. I've removed your number from our list. Have a good day."),
        ],
    },
    "Hindi": {
        "open": [
            ("agent", "नमस्ते {name} जी, मैं {business} से प्रिया बोल रही हूँ। क्या आपके पास एक मिनट है?"),
            ("user", "हाँ, बताइए।"),
            ("agent", "धन्यवाद! मैं {pitch} के बारे में बात करना चाहती थी। क्या आपको इसमें रुचि होगी?"),
        ],
        "success": [
            ("user", "हाँ, बिल्कुल। इसका खर्च कितना होगा?"),
            ("agent", "वो आपकी पसंद पर निर्भर करता है। हमारी टीम आपको सारे ऑप्शन समझा देगी, कोई बाध्यता नहीं। क्या शनिवार सुबह 11 बजे ठीक रहेगा?"),
            ("user", "शनिवार ठीक है, बुक कर दीजिए।"),
            ("agent", "हो गया! शनिवार सुबह 11 बजे के लिए आपकी बुकिंग पक्की है। आपको SMS पर कन्फ़र्मेशन मिल जाएगा। धन्यवाद {name} जी!"),
        ],
        "not_interested": [
            ("user", "अभी नहीं, अभी ज़रूरत नहीं है।"),
            ("agent", "कोई बात नहीं। आगे कभी ज़रूरत हो तो हमें ज़रूर बताइए। धन्यवाद!"),
        ],
        "callback": [
            ("user", "अभी मैं थोड़ा बिज़ी हूँ, शाम को कॉल कर सकते हैं?"),
            ("agent", "ज़रूर, हम आज शाम 6 बजे के बाद आपको दोबारा कॉल करेंगे। धन्यवाद!"),
        ],
        "opt_out": [
            ("user", "मुझे ऐसे कॉल मत कीजिए।"),
            ("agent", "माफ़ कीजिए। मैंने आपका नंबर हमारी लिस्ट से हटा दिया है। आपका दिन शुभ हो।"),
        ],
    },
    "Telugu": {
        "open": [
            ("agent", "నమస్కారం {name} గారు, నేను {business} నుండి ప్రియ మాట్లాడుతున్నాను. ఒక్క నిమిషం మాట్లాడవచ్చా?"),
            ("user", "అవును, చెప్పండి."),
            ("agent", "ధన్యవాదాలు! {pitch} గురించి మాట్లాడాలనుకుంటున్నాను. మీకు ఆసక్తి ఉందా?"),
        ],
        "success": [
            ("user", "అవును, ఉంది. దీనికి ఖర్చు ఎంత అవుతుంది?"),
            ("agent", "అది మీరు ఎంచుకునే దాన్ని బట్టి ఉంటుంది. మా టీమ్ అన్ని ఆప్షన్లు వివరంగా చెబుతుంది, ఎలాంటి ఒత్తిడి లేదు. శనివారం ఉదయం 11 గంటలకు కుదురుతుందా?"),
            ("user", "శనివారం సరే, బుక్ చేయండి."),
            ("agent", "అయిపోయింది! శనివారం ఉదయం 11 గంటలకు మీ బుకింగ్ ఖాయం. మీకు SMS లో కన్ఫర్మేషన్ వస్తుంది. ధన్యవాదాలు {name} గారు!"),
        ],
        "not_interested": [
            ("user", "ఇప్పుడు వద్దండి, అవసరం లేదు."),
            ("agent", "పర్వాలేదు. తర్వాత అవసరమైతే మాకు తప్పకుండా చెప్పండి. ధన్యవాదాలు!"),
        ],
        "callback": [
            ("user", "ఇప్పుడు కొంచెం బిజీగా ఉన్నాను, సాయంత్రం కాల్ చేయగలరా?"),
            ("agent", "తప్పకుండా, ఈ రోజు సాయంత్రం 6 తర్వాత మళ్ళీ కాల్ చేస్తాం. ధన్యవాదాలు!"),
        ],
        "opt_out": [
            ("user", "దయచేసి ఇలాంటి కాల్స్ చేయకండి."),
            ("agent", "క్షమించండి. మీ నంబర్‌ను మా లిస్ట్ నుండి తీసేశాను. మంచి రోజు!"),
        ],
    },
}

_SIM_SUMMARIES = {
    "success": "Interested. Asked about cost; booked for Saturday 11 AM. SMS confirmation sent.",
    "not_interested": "Not interested right now. Invited to call back if needs change.",
    "callback": "Busy; asked for a call back after 6 PM today.",
    "opt_out": "Asked not to be called again. Added to the do-not-call list.",
}


def _sim_rng(contact: CampaignContact) -> random.Random:
    seed = int(hashlib.sha256(f"{contact.id}:{contact.attempts}".encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def plan_simulated_call(campaign: CallCampaign, contact: CampaignContact, now: datetime) -> dict[str, Any]:
    """Decide, deterministically per contact, how its simulated call goes and how long it takes."""
    rng = _sim_rng(contact)
    roll = rng.random()
    speed = max(campaign.sim_speed or 1.0, 0.1)
    if roll < 0.20:
        status, ring, talk = ContactStatus.NO_ANSWER, rng.uniform(25, 35), 0.0
    elif roll < 0.26:
        status, ring, talk = ContactStatus.BUSY, rng.uniform(3, 8), 0.0
    elif roll < 0.28:
        status, ring, talk = ContactStatus.FAILED, rng.uniform(2, 5), 0.0
    else:
        status, ring = ContactStatus.CONNECTED, rng.uniform(4, 12)
        talk = 0.0
    branch = None
    if status == ContactStatus.CONNECTED:
        r = rng.random()
        branch = "success" if r < 0.42 else "not_interested" if r < 0.74 else "callback" if r < 0.94 else "opt_out"
        talk = {"success": rng.uniform(70, 140), "not_interested": rng.uniform(25, 50),
                "callback": rng.uniform(20, 40), "opt_out": rng.uniform(15, 30)}[branch]
    language = contact.language or campaign.language
    if language not in _SCRIPTS:
        language = "English"
    total = (ring + talk) / speed
    return {
        "status": status,
        "branch": branch,
        "language": language,
        "ring_s": round(ring / speed, 2),
        "talk_s": round(talk, 1),
        "ends_at": (now + timedelta(seconds=total)).isoformat(),
        "started_at": now.isoformat(),
    }


def simulated_transcript(campaign: CallCampaign, contact: CampaignContact, plan: dict[str, Any]) -> list[dict[str, str]]:
    if plan.get("status") != ContactStatus.CONNECTED or not plan.get("branch"):
        return []
    script = _SCRIPTS[plan["language"]]
    fill = {
        "name": (contact.name or "").split(" ")[0] or ("Sir" if plan["language"] == "English" else ""),
        "business": campaign.business_name or "our team",
        "pitch": campaign.pitch or campaign.goal,
    }
    turns = script["open"] + script[plan["branch"]]
    return [
        {"role": role, "content": text.format(**fill).replace("  ", " "), "language": plan["language"]}
        for role, text in turns
    ]


def live_progress(campaign: CallCampaign, contact: CampaignContact, now: datetime) -> dict[str, Any]:
    """What an in-flight call is doing right now, for the live board."""
    plan = contact.sim_plan
    started = contact.dialed_at or now
    elapsed = max((now - started).total_seconds(), 0.0)
    if not plan:
        # Live calls report nothing until they end; Samvaad has no mid-call feed.
        return {"phase": "in_call" if elapsed > 20 else "ringing", "elapsed_seconds": int(elapsed), "line": None}
    ring = float(plan.get("ring_s") or 0)
    if elapsed < ring or plan.get("status") != ContactStatus.CONNECTED:
        return {"phase": "ringing", "elapsed_seconds": int(elapsed), "line": None}
    ends = datetime.fromisoformat(plan["ends_at"])
    talk_real = max((ends - started).total_seconds() - ring, 0.1)
    frac = min((elapsed - ring) / talk_real, 1.0)
    turns = simulated_transcript(campaign, contact, plan)
    shown = turns[: max(1, math.ceil(frac * len(turns)))]
    return {"phase": "in_call", "elapsed_seconds": int(elapsed), "line": shown[-1] if shown else None}


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

async def _lock_campaign(session: AsyncSession, campaign_id: Any) -> CallCampaign | None:
    row = await session.execute(
        select(CallCampaign).where(CallCampaign.id == campaign_id).with_for_update().execution_options(populate_existing=True)
    )
    return row.scalar_one_or_none()


async def _settle_simulated(session: AsyncSession, campaign: CallCampaign, now: datetime) -> None:
    rows = await session.execute(
        select(CampaignContact).where(
            CampaignContact.campaign_id == campaign.id, CampaignContact.status == ContactStatus.DIALING
        )
    )
    for contact in rows.scalars().all():
        plan = contact.sim_plan or {}
        if not plan or datetime.fromisoformat(plan["ends_at"]) > now:
            continue
        transcript = simulated_transcript(campaign, contact, plan)
        branch = plan.get("branch")
        final_vars: dict[str, Any] = {}
        if branch == "success":
            final_vars[campaign.success_variable] = (campaign.success_values or ["true"])[0]
        if branch == "opt_out":
            final_vars["opt_out"] = "true"
        await apply_outcome(
            session,
            campaign,
            contact,
            status=plan["status"],
            duration=plan.get("talk_s") or None,
            final_vars=final_vars,
            transcript=transcript,
            summary=_SIM_SUMMARIES.get(branch or "") or summarize(plan["status"], None, None),
        )


async def _expire_stale_live(session: AsyncSession, campaign: CallCampaign, now: datetime) -> None:
    rows = await session.execute(
        select(CampaignContact).where(
            CampaignContact.campaign_id == campaign.id,
            CampaignContact.status == ContactStatus.DIALING,
            CampaignContact.dialed_at < now - LIVE_CALL_TIMEOUT,
        )
    )
    for contact in rows.scalars().all():
        await apply_outcome(
            session, campaign, contact, status=ContactStatus.FAILED, duration=None, final_vars=None,
            transcript=None, summary="No outcome reported by the calling platform.",
        )


async def counts(session: AsyncSession, campaign_id: Any) -> dict[str, int]:
    rows = await session.execute(
        select(CampaignContact.status, func.count())
        .where(CampaignContact.campaign_id == campaign_id)
        .group_by(CampaignContact.status)
    )
    return {status: n for status, n in rows.all()}


def _max_concurrency(campaign: CallCampaign) -> int:
    cap = settings.campaign_max_concurrency_sim if campaign.mode == "simulation" else settings.campaign_max_concurrency
    return max(1, min(campaign.concurrency, cap))


async def _finish_if_done(session: AsyncSession, campaign: CallCampaign, by_status: dict[str, int], now: datetime) -> None:
    if campaign.status != CampaignStatus.RUNNING:
        return
    if campaign.success_count >= campaign.target_count:
        campaign.status = CampaignStatus.TARGET_REACHED
    elif by_status.get(ContactStatus.PENDING, 0) == 0 and by_status.get(ContactStatus.DIALING, 0) == 0:
        campaign.status = CampaignStatus.COMPLETED
    else:
        return
    campaign.finished_at = now
    campaign.hold_reason = None
    # Nobody left in the queue gets a call once the goal is met.
    await session.execute(
        update(CampaignContact)
        .where(CampaignContact.campaign_id == campaign.id, CampaignContact.status == ContactStatus.PENDING)
        .values(status=ContactStatus.SKIPPED, summary="Not called: the campaign reached its goal.")
    )
    logger.info("Campaign %s finished: %s (%d successes)", campaign.id, campaign.status, campaign.success_count)


async def _hold(campaign: CallCampaign, session: AsyncSession, now: datetime) -> str | None:
    """Why this campaign may not dial right now, or None."""
    if campaign.mode == "simulation":
        return None
    if not in_calling_window(campaign, now):
        start = max(campaign.window_start_hour, LEGAL_START_HOUR)
        end = min(campaign.window_end_hour, LEGAL_END_HOUR)
        return f"Waiting for calling hours ({start}:00 to {end}:00 IST)"
    wallet = await BillingService(session).get_wallet(campaign.tenant_id)
    if wallet is None or wallet.call_balance_paise <= 0 or wallet.deployment_status == STATUS_PAUSED_ZERO:
        return "Out of call credit. Add credit to keep calling."
    return None


async def advance(session: AsyncSession, campaign_id: Any, webhook_url_for: WebhookUrlFor | None) -> CallCampaign | None:
    """Settle finished calls and dial more, up to the concurrency limit. Commits."""
    campaign = await _lock_campaign(session, campaign_id)
    if campaign is None:
        return None
    now = utcnow_naive()
    if campaign.mode == "simulation":
        await _settle_simulated(session, campaign, now)
    else:
        await _expire_stale_live(session, campaign, now)
    await session.flush()

    by_status = await counts(session, campaign.id)
    await _finish_if_done(session, campaign, by_status, now)
    if campaign.status != CampaignStatus.RUNNING:
        await session.commit()
        return campaign

    hold = await _hold(campaign, session, now)
    campaign.hold_reason = hold
    free = _max_concurrency(campaign) - by_status.get(ContactStatus.DIALING, 0)
    if hold or free <= 0:
        await session.commit()
        return campaign

    batch = min(free, SIM_DIALS_PER_TICK if campaign.mode == "simulation" else LIVE_DIALS_PER_TICK)
    rows = await session.execute(
        select(CampaignContact)
        .where(CampaignContact.campaign_id == campaign.id, CampaignContact.status == ContactStatus.PENDING)
        .order_by(CampaignContact.attempts, CampaignContact.position)
        .limit(batch)
    )
    contacts = list(rows.scalars().all())
    blocked = await _blocked_numbers(session, campaign.tenant_id, [c.phone for c in contacts])
    to_dial = []
    for contact in contacts:
        if contact.phone in blocked:
            contact.status = ContactStatus.SUPPRESSED
            contact.summary = "Not called: on the do-not-call list."
            continue
        to_dial.append(contact)

    if campaign.mode == "simulation":
        for contact in to_dial:
            contact.status = ContactStatus.DIALING
            contact.attempts += 1
            contact.dialed_at = now
            contact.sim_plan = plan_simulated_call(campaign, contact, now)
        await session.commit()
        return campaign

    await _dial_live(session, campaign, to_dial, now, webhook_url_for)
    return campaign


async def _blocked_numbers(session: AsyncSession, tenant_id: str, phones: list[str]) -> set[str]:
    if not phones:
        return set()
    rows = await session.execute(
        select(DoNotCallEntry.phone).where(DoNotCallEntry.tenant_id == tenant_id, DoNotCallEntry.phone.in_(phones))
    )
    return set(rows.scalars().all())


async def _dial_live(
    session: AsyncSession,
    campaign: CallCampaign,
    contacts: list[CampaignContact],
    now: datetime,
    webhook_url_for: WebhookUrlFor | None,
) -> None:
    if not contacts or webhook_url_for is None:
        await session.commit()
        return
    binding = (
        await session.execute(
            select(SamvaadAgentBinding).where(
                SamvaadAgentBinding.tenant_id == campaign.tenant_id, SamvaadAgentBinding.app_id == campaign.app_id
            )
        )
    ).scalar_one_or_none()
    if binding is None or not (binding.connection_id and binding.agent_phone_number and binding.app_version):
        campaign.status = CampaignStatus.PAUSED
        campaign.hold_reason = "The agent for this campaign has no outbound number any more."
        await session.commit()
        return
    app_id, app_version = binding.app_id, binding.app_version
    connection_id, agent_number = binding.connection_id, binding.agent_phone_number

    jobs = []
    for contact in contacts:
        token = secrets.token_urlsafe(32)
        attempt = SamvaadCallAttempt(
            tenant_id=campaign.tenant_id,
            actor_id=campaign.created_by,
            app_id=app_id,
            app_version=app_version,
            user_phone_masked=mask_phone(contact.phone),
            webhook_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        )
        session.add(attempt)
        await session.flush()
        contact.status = ContactStatus.DIALING
        contact.attempts += 1
        contact.dialed_at = now
        contact.call_id = attempt.id
        jobs.append((contact, attempt, token))
    # Committed before dialling, so a webhook that beats our response finds its row.
    await session.commit()

    client = SamvaadClient()
    gate = asyncio.Semaphore(10)

    async def place(contact: CampaignContact, attempt: SamvaadCallAttempt, token: str) -> str | HTTPException:
        variables = {
            "name": contact.name,
            "business_name": campaign.business_name,
            "goal": campaign.goal,
            "pitch": campaign.pitch or "",
            **(contact.variables or {}),
        }
        overrides: dict[str, Any] = {"initial_language_name": contact.language or campaign.language}
        if campaign.opening_line:
            overrides["initial_bot_message"] = campaign.opening_line.replace("{name}", contact.name or "")[:500]
        async with gate:
            try:
                return await client.create_outbound_call(
                    app_id=app_id,
                    app_version=app_version,
                    connection_id=connection_id,
                    agent_phone_number=agent_number,
                    user_phone_number=contact.phone,
                    webhook_url=webhook_url_for(token),
                    webhook_metadata={"call_id": str(attempt.id), "campaign_id": str(campaign.id)},
                    agent_variables=variables,
                    overrides=overrides,
                )
            except HTTPException as exc:
                return exc

    results = await asyncio.gather(*(place(c, a, t) for c, a, t in jobs))
    for (contact, attempt, _), result in zip(jobs, results):
        if isinstance(result, str):
            attempt.attempt_id = result
            continue
        attempt.status = SamvaadCallStatus.FAILED
        attempt.failure_reason = f"not placed: {result.detail}"[:500]
        attempt.completed_at = utcnow_naive()
        if result.status_code == 429:
            # The platform is full; put the contact back and try on a later tick.
            contact.status = ContactStatus.PENDING
            contact.attempts = max(contact.attempts - 1, 0)
            contact.call_id = None
            campaign.hold_reason = "Calling platform is busy; retrying shortly."
        else:
            await apply_outcome(
                session, campaign, contact, status=ContactStatus.FAILED, duration=None, final_vars=None,
                transcript=None, summary=f"Could not place the call: {result.detail}"[:500],
            )
    await session.commit()
    placed = sum(isinstance(r, str) for r in results)
    logger.info("Campaign %s placed %d/%d calls", campaign.id, placed, len(jobs))


# ---------------------------------------------------------------------------
# Comparison with a human telecaller
# ---------------------------------------------------------------------------

def versus_telecaller(
    contacts_done: list[tuple[str, float | None]],
    started_at: datetime | None,
    finished_at: datetime | None,
    now: datetime,
    speed: float = 1.0,
) -> dict[str, Any]:
    """How long one person would need for the calls finished so far.

    A telecaller dials one number at a time: every call costs its talk time (or
    ~30 s of ringing) plus about a minute to dial and write notes.
    """
    human = 0.0
    for status, duration in contacts_done:
        if status == ContactStatus.CONNECTED:
            human += (duration or 0) + HUMAN_OVERHEAD_SECONDS
        elif status in (ContactStatus.NO_ANSWER, ContactStatus.BUSY, ContactStatus.FAILED):
            human += HUMAN_RING_SECONDS + HUMAN_OVERHEAD_SECONDS
    elapsed = ((finished_at or now) - started_at).total_seconds() if started_at else 0.0
    # A sped-up simulation is compared at real-world pace, never flattered by the speed-up.
    elapsed *= max(speed, 1.0)
    return {
        "calls_finished": len(contacts_done),
        "ai_elapsed_seconds": int(max(elapsed, 0)),
        "one_telecaller_seconds": int(human),
        # How many people dialling at once it would take to keep this pace.
        "telecallers_to_match": math.ceil(human / elapsed) if elapsed > 0 and human > 0 else 0,
        "assumptions": "One telecaller dials one number at a time: talk time (or 30 s ringing) plus 60 s to dial and take notes per call.",
    }
