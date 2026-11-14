"""Scheduled AI calls: a plan of call slots, and a loop that dials each one when it is due.

`plan_calls` spreads prospects over working days in the hours owners usually pick up
(11:00-13:00 and 15:30-18:00 IST), best-fit firms first, at most `per_day` a day.
`dial_due` runs inside `serve` every minute. At each slot it checks every rule again
(live mode, approval, DND scrub, opt-out, contact hours, frequency, daily cap) and only then dials.
A temporary block (outside hours, daily cap) moves the call to the next slot; a permanent one
(opted out, on DND, not approved, no scrub) skips it with the reason.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from .compliance import IST, can_contact
from .config import Settings
from .store import Store, iso, utcnow

log = logging.getLogger("fieldos_sales.scheduler")

WINDOWS = [(time(11, 0), time(13, 0)), (time(15, 30), time(18, 0))]
PERMANENT = ("opted out", "DND", "not approved", "no DND scrub", "scrub older", "not an Indian", "does not belong",
             "already called")

SCHEMA = """
CREATE TABLE IF NOT EXISTS call_schedule (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    phone TEXT NOT NULL,
    slot_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',   -- scheduled / dialled / skipped / cancelled
    reason TEXT,
    call_sid TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS call_schedule_due ON call_schedule(status, slot_at);
"""


def ensure(store: Store) -> None:
    with store._lock:
        store.conn.executescript(SCHEMA)


def _slots(day: date, n: int) -> list[datetime]:
    minutes = [(datetime.combine(day, a), datetime.combine(day, b)) for a, b in WINDOWS]
    total = sum((b - a).total_seconds() for a, b in minutes)
    out = []
    for i in range(n):
        offset = total * (i + 0.5) / n
        for a, b in minutes:
            span = (b - a).total_seconds()
            if offset < span:
                out.append((a + timedelta(seconds=offset)).replace(second=0, microsecond=0, tzinfo=IST))
                break
            offset -= span
    return out


def _rank(p: dict[str, Any]) -> tuple:
    prio = (p.get("priority") or "C")[:1].upper()
    mobile_first = 0 if any(ph[3:4] in "6789" and not ph.startswith("+9180") for ph in p["phones"]) else 1
    return ("ABC".find(prio) if prio in "ABC" else 3, mobile_first, p["id"])


def plan_calls(store: Store, settings: Settings, prospects: list[dict[str, Any]], start: date | None = None,
               per_day: int | None = None) -> list[dict[str, Any]]:
    """Give each prospect (with a phone, not opted out, not already scheduled) one call slot."""
    ensure(store)
    per_day = min(per_day or settings.calls_per_day, settings.calls_per_day)
    taken = {r["prospect_id"] for r in store.all("SELECT prospect_id FROM call_schedule WHERE status = 'scheduled'")}
    todo = [p for p in sorted(prospects, key=_rank)
            if p["phones"] and p["id"] not in taken and not all(store.is_suppressed(ph) for ph in p["phones"])]
    day = start or (utcnow().astimezone(IST) + timedelta(days=1)).date()
    planned = []
    while todo:
        if day.strftime("%a") in settings.call_days and day.strftime("%a") in settings.contact_days:
            for slot in _slots(day, min(per_day, len(todo))):
                p = todo.pop(0)
                phone = next((ph for ph in p["phones"] if not store.is_suppressed(ph)), p["phones"][0])
                store.execute("INSERT INTO call_schedule (prospect_id, phone, slot_at, created_at) VALUES (?, ?, ?, ?)",
                              (p["id"], phone, iso(slot), iso()))
                planned.append({"prospect_id": p["id"], "firm": p["firm"], "phone": phone, "slot": slot})
        day += timedelta(days=1)
    return planned


def cancel_all(store: Store) -> int:
    ensure(store)
    cur = store.execute("UPDATE call_schedule SET status = 'cancelled' WHERE status = 'scheduled'")
    return cur.rowcount


def dial_due(store: Store, settings: Settings, dial, now: datetime | None = None) -> list[str]:
    """Dial every scheduled call whose slot has come, if all checks pass now. `dial(phone, pid) -> sid`."""
    ensure(store)
    now = now or utcnow()
    report = []
    for row in store.all("SELECT * FROM call_schedule WHERE status = 'scheduled' AND slot_at <= ? ORDER BY slot_at",
                         (iso(now),)):
        prospect = store.prospect(row["prospect_id"])
        decision = can_contact(store, settings, prospect, row["phone"], "call", now) if prospect else None
        if decision is None or not decision.ok:
            reasons = decision.reasons if decision is not None else ["prospect missing"]
            if decision is None or any(k in r for r in reasons for k in PERMANENT):
                store.execute("UPDATE call_schedule SET status = 'skipped', reason = ? WHERE id = ?", ("; ".join(reasons), row["id"]))
                report.append(f"skipped #{row['id']} {prospect['firm'] if prospect else '?'}: {'; '.join(reasons)}")
            else:
                nxt = _next_slot(settings, now)
                store.execute("UPDATE call_schedule SET slot_at = ?, reason = ? WHERE id = ?", (iso(nxt), "; ".join(reasons), row["id"]))
                report.append(f"moved #{row['id']} to {nxt:%a %d %b %H:%M}: {'; '.join(reasons)}")
            continue
        try:
            sid = dial(row["phone"], row["prospect_id"])
        except Exception as e:  # provider error: try again at the next slot
            store.execute("UPDATE call_schedule SET slot_at = ?, reason = ? WHERE id = ?",
                          (iso(_next_slot(settings, now)), f"dial failed: {e}"[:300], row["id"]))
            report.append(f"dial failed #{row['id']}: {e}")
            continue
        store.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
                      (sid, row["prospect_id"], row["phone"], iso()))
        store.log("call", "out", prospect_id=row["prospect_id"], phone=row["phone"], outcome="dialled", meta={"call_sid": sid, "scheduled": row["id"]})
        store.execute("UPDATE call_schedule SET status = 'dialled', call_sid = ? WHERE id = ?", (sid, row["id"]))
        report.append(f"dialled #{row['id']} {prospect['firm']} ({sid})")
        break  # one call at a time; the next due one goes on the next tick
    return report


def _next_slot(settings: Settings, now: datetime) -> datetime:
    local = now.astimezone(IST)
    for d in range(8):
        day = (local + timedelta(days=d)).date()
        if day.strftime("%a") not in settings.call_days or day.strftime("%a") not in settings.contact_days:
            continue
        for a, b in WINDOWS:
            start = datetime.combine(day, a, tzinfo=IST)
            end = datetime.combine(day, b, tzinfo=IST)
            if local < start:
                return start
            if start <= local < end and d == 0:
                return min(end, local + timedelta(minutes=30))
    return local + timedelta(days=1)


async def scheduler_loop(store: Store, settings: Settings, stop: asyncio.Event, dial=None) -> None:
    if not settings.live:
        log.warning("live mode is off: scheduled calls are not dialled")
        return
    if dial is None and settings.uses_samvaad:
        from .samvaad import SamvaadDialer, make_dial
        missing = SamvaadDialer(settings).configured()
        if missing:
            log.warning("Samvaad not configured (%s): scheduled calls are not dialled", ", ".join(missing))
            return
        dial = make_dial(store, settings)
    if dial is None:
        from .telephony import ExotelDialer
        dialer = ExotelDialer(settings)
        if dialer.configured():
            log.warning("Exotel not configured: scheduled calls are not dialled")
            return
        dial = dialer.dial
    while not stop.is_set():
        for line in await asyncio.to_thread(dial_due, store, settings, dial):
            log.info(line)
        try:
            await asyncio.wait_for(stop.wait(), timeout=90)  # also leaves room for the current call
        except TimeoutError:
            pass
