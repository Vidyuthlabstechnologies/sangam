"""Can we contact this number, on this channel, right now?

Every real call and every real WhatsApp message goes through can_contact().
It fails closed: missing data means "no".

Checks, in order:
  live switch          FIELDOS_SALES_LIVE=1 must be set
  approval             the owner approved this prospect for this channel
  number               a valid Indian number (a mobile for WhatsApp)
  opt-out              never contact a number that asked us to stop
  DND / NCPR           calls need a fresh "not registered" scrub result;
                       any channel is blocked if the number is on DND
  contact hours        IST, configured days and hours only
  frequency            calls: no repeat within 7 days, 2 attempts max;
                       WhatsApp: one opener + one follow-up without a reply
  daily cap            calls per day / new WhatsApp chats per day
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .prospects import is_indian_mobile, normalise_indian_phone
from .store import Store, utcnow

IST = timezone(timedelta(hours=5, minutes=30))
CALL_MIN_GAP = timedelta(days=7)
CALL_MAX_ATTEMPTS = 2
WA_MAX_UNANSWERED = 2


@dataclass
class Decision:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def within_contact_hours(settings: Settings, now: datetime | None = None, channel: str = "whatsapp") -> bool:
    local = (now or utcnow()).astimezone(IST)
    start, end = settings.contact_hours
    days = settings.call_days if channel == "call" else settings.contact_days
    return local.strftime("%a") in days and local.strftime("%a") in settings.contact_days and start <= local.hour < end


def _count_today(store: Store, sql: str, now: datetime) -> int:
    local_midnight = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    row = store.one(sql, (local_midnight.astimezone(UTC).isoformat(timespec="seconds"),))
    return int(row[0]) if row else 0


def can_contact(store: Store, settings: Settings, prospect: dict, phone: str, channel: str,
                now: datetime | None = None, *, check_approval: bool = True,
                check_live: bool = True) -> Decision:
    now = now or utcnow()
    reasons: list[str] = []

    if check_live and not settings.live:
        reasons.append("live mode is off (set FIELDOS_SALES_LIVE=1)")
    if check_approval and not store.is_approved(prospect["id"], channel):
        reasons.append(f"not approved for {channel} (run: approve --channel {channel} --ids {prospect['id']})")
    if phone not in prospect.get("phones", []):
        reasons.append("number does not belong to this prospect")
    if channel == "whatsapp" and not is_indian_mobile(phone):
        reasons.append("not an Indian mobile number")
    elif not phone.startswith("+91"):
        reasons.append("not an Indian number")
    if store.is_suppressed(phone):
        reasons.append("number opted out")

    if _self_test(settings, prospect, phone):
        # Your own phone (TEST_NUMBERS): skip hours, DND scrub, frequency and caps. Live mode,
        # approval and opt-out above still apply.
        return Decision(ok=not reasons, reasons=reasons)

    dnd = store.dnd(phone)
    if dnd is not None and dnd["registered"]:
        reasons.append("number is on the DND / NCPR register")
    elif channel == "call":
        if dnd is None:
            reasons.append("no DND scrub result for this number (run: import-dnd)")
        elif now - _parse(dnd["checked_at"]) > timedelta(days=settings.dnd_max_age_days):
            reasons.append(f"DND scrub older than {settings.dnd_max_age_days} days; scrub again")

    if not within_contact_hours(settings, now, channel):
        s, e = settings.contact_hours
        days = [d for d in (settings.call_days if channel == "call" else settings.contact_days) if d in settings.contact_days]
        reasons.append(f"outside contact hours ({','.join(days)} {s}:00-{e}:00 IST)")

    if channel == "call":
        calls = store.all(
            "SELECT created_at FROM touches WHERE prospect_id = ? AND channel = 'call' AND direction = 'out' AND outcome = 'dialled' ORDER BY id",
            (prospect["id"],),
        )
        asked_callback = store.one(
            "SELECT 1 FROM touches WHERE prospect_id = ? AND outcome = 'callback_later'", (prospect["id"],)
        ) is not None
        if len(calls) >= CALL_MAX_ATTEMPTS and not asked_callback:
            reasons.append(f"already called {len(calls)} times")
        if calls and now - _parse(calls[-1]["created_at"]) < CALL_MIN_GAP and not asked_callback:
            reasons.append("called in the last 7 days")
        if _count_today(store, "SELECT COUNT(*) FROM touches WHERE channel = 'call' AND direction = 'out' AND outcome = 'dialled' AND created_at >= ?", now) >= settings.calls_per_day:
            reasons.append(f"daily call cap reached ({settings.calls_per_day})")
    else:
        last_in = store.one(
            "SELECT MAX(id) AS m FROM touches WHERE phone = ? AND channel = 'whatsapp' AND direction = 'in'", (phone,)
        )
        last_in_id = (last_in["m"] if last_in else None) or 0
        unanswered = store.one(
            "SELECT COUNT(*) FROM touches WHERE phone = ? AND channel = 'whatsapp' AND direction = 'out' AND outcome = 'sent' AND id > ?",
            (phone, last_in_id),
        )[0]
        if unanswered >= WA_MAX_UNANSWERED:
            reasons.append(f"{unanswered} messages with no reply; stop")
        is_new_chat = store.one(
            "SELECT 1 FROM touches WHERE phone = ? AND channel = 'whatsapp' AND outcome = 'sent'", (phone,)
        ) is None
        if is_new_chat and _count_today(
            store,
            "SELECT COUNT(*) FROM wa_outbox WHERE status = 'sent' AND kind = 'opener' AND sent_at >= ?", now,
        ) >= settings.wa_new_chats_per_day:
            reasons.append(f"daily new-chat cap reached ({settings.wa_new_chats_per_day})")

    return Decision(ok=not reasons, reasons=reasons)


def _self_test(settings: Settings, prospect: dict, phone: str) -> bool:
    from .selftest import is_test
    return is_test(settings, prospect, phone)


def import_dnd_csv(store: Store, path: Path, checked_at: datetime | None = None) -> tuple[int, int]:
    """Load a scrub result file: columns phone, dnd (yes/no/1/0/true/false).

    Get it from your telemarketer / operator scrub (DLT portal) or your
    calling provider's DND check. Rows we cannot read are skipped, which
    leaves the number blocked for calls.
    """
    total = registered = 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = {k.lower().strip(): k for k in (reader.fieldnames or [])}
        phone_col = fields.get("phone") or fields.get("number") or fields.get("msisdn")
        dnd_col = fields.get("dnd") or fields.get("registered") or fields.get("status")
        if not phone_col or not dnd_col:
            raise ValueError("CSV needs a 'phone' and a 'dnd' column")
        for row in reader:
            phone = normalise_indian_phone(row.get(phone_col, ""))
            value = (row.get(dnd_col) or "").strip().lower()
            if not phone or value not in {"yes", "no", "1", "0", "true", "false", "registered", "not registered", "y", "n"}:
                continue
            is_dnd = value in {"yes", "1", "true", "registered", "y"}
            store.set_dnd(phone, is_dnd, checked_at)
            total += 1
            registered += int(is_dnd)
    return total, registered
