"""WhatsApp: gateways, the slow outbox sender, and replies to prospects.

Gateways
  waha    WAHA (WhatsApp HTTP API, self-hosted, scan a QR with your own number).
          Unofficial: WhatsApp can ban the number. Use a separate SIM, keep the
          daily caps low, and only message firms you have approved.
  twilio  Official WhatsApp Business API through Twilio. Cold first messages
          need a Meta-approved template; free-form text only works within 24 h
          of the prospect writing to you.
  dry     Prints instead of sending. Used whenever live mode is off.

The bot only ever talks to numbers that belong to imported prospects. Every
other chat on the number (friends, family, groups) is ignored.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import random
from datetime import timedelta
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from . import guardrails
from .compliance import can_contact
from .config import Settings
from .conversation import DISCLOSURE, Conversation
from .llm import LLM
from .prospects import normalise_indian_phone
from .store import Store, iso, utcnow

log = logging.getLogger("fieldos_sales.whatsapp")

FOLLOW_UP = (
    "Namaste again from the FieldOS team. Just checking if you'd like a short 30-minute walkthrough of how "
    "supervisors record attendance, deliveries and spending from site, even with no signal. If now isn't the "
    "right time, no problem at all. Reply STOP and we won't message again 🙏"
)
PERMANENT_BLOCKS = ("opted out", "DND", "not approved", "no reply", "not an Indian", "does not belong")


class Gateway(Protocol):
    name: str
    async def exists(self, phone: str) -> bool: ...
    async def typing(self, phone: str, seconds: float) -> None: ...
    async def send(self, phone: str, text: str) -> None: ...


def _digits(phone: str) -> str:
    return phone.lstrip("+")


class WahaGateway:
    name = "waha"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.s = settings
        self.client = client or httpx.AsyncClient(timeout=30)
        self.headers = {"X-Api-Key": settings.waha_api_key} if settings.waha_api_key else {}

    def _chat(self, phone: str) -> str:
        return f"{_digits(phone)}@c.us"

    async def exists(self, phone: str) -> bool:
        r = await self.client.get(f"{self.s.waha_url}/api/contacts/check-exists",
                                  params={"phone": _digits(phone), "session": self.s.waha_session}, headers=self.headers)
        r.raise_for_status()
        return bool(r.json().get("numberExists"))

    async def typing(self, phone: str, seconds: float) -> None:
        body = {"session": self.s.waha_session, "chatId": self._chat(phone)}
        try:
            await self.client.post(f"{self.s.waha_url}/api/startTyping", json=body, headers=self.headers)
            await asyncio.sleep(seconds)
            await self.client.post(f"{self.s.waha_url}/api/stopTyping", json=body, headers=self.headers)
        except httpx.HTTPError:
            pass  # typing is cosmetic

    async def send(self, phone: str, text: str) -> None:
        r = await self.client.post(f"{self.s.waha_url}/api/sendText", headers=self.headers,
                                   json={"session": self.s.waha_session, "chatId": self._chat(phone), "text": text})
        r.raise_for_status()


class TwilioGateway:
    name = "twilio"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.s = settings
        self.client = client or httpx.AsyncClient(timeout=30)

    async def exists(self, phone: str) -> bool:
        return True  # Twilio reports undeliverable numbers after sending

    async def typing(self, phone: str, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def send(self, phone: str, text: str) -> None:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.s.twilio_account_sid}/Messages.json"
        r = await self.client.post(url, auth=(self.s.twilio_account_sid, self.s.twilio_auth_token),
                                   data={"From": f"whatsapp:{self.s.twilio_whatsapp_from}", "To": f"whatsapp:{phone}", "Body": text})
        r.raise_for_status()


class DryGateway:
    name = "dry"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def exists(self, phone: str) -> bool:
        return True

    async def typing(self, phone: str, seconds: float) -> None:
        return None

    async def send(self, phone: str, text: str) -> None:
        self.sent.append((phone, text))
        log.info("[dry run] would send to %s: %s", phone, text)


def make_gateway(settings: Settings) -> Gateway:
    if not settings.live:
        return DryGateway()
    if settings.whatsapp_gateway == "twilio":
        return TwilioGateway(settings)
    return WahaGateway(settings)


def twilio_signature_ok(auth_token: str, url: str, params: dict[str, str], signature: str) -> bool:
    payload = url + "".join(k + params[k] for k in sorted(params))
    digest = base64.b64encode(hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(digest, signature or "")


def parse_waha_event(event: dict[str, Any]) -> tuple[str, str] | None:
    """(phone, text) for a direct text message from someone else; None for anything else."""
    if event.get("event") not in ("message", "message.any"):
        return None
    p = event.get("payload") or {}
    sender = str(p.get("from") or "")
    if p.get("fromMe") or not sender.endswith("@c.us"):
        return None  # our own messages, groups (@g.us), status updates, channels
    text = (p.get("body") or "").strip()
    phone = normalise_indian_phone(sender.split("@")[0])
    return (phone, text) if phone and text else None


# ---- outbox ---------------------------------------------------------------------
def queue_openers(store: Store, prospect_ids: list[int]) -> list[str]:
    report = []
    for pid in prospect_ids:
        p = store.prospect(pid)
        if not p:
            report.append(f"{pid}: no such prospect")
            continue
        text = store.draft(pid, "wa_opener")
        mobiles = [ph for ph in p["phones"] if ph[3] in "6789"]
        if not text:
            report.append(f"{pid} {p['firm']}: no WhatsApp draft (run: pitch)")
        elif not store.is_approved(pid, "whatsapp"):
            report.append(f"{pid} {p['firm']}: not approved for WhatsApp")
        elif not mobiles:
            report.append(f"{pid} {p['firm']}: no mobile number")
        elif guardrails.check_outbound(text):
            report.append(f"{pid} {p['firm']}: draft fails the pricing check; rewrite it")
        elif store.one("SELECT 1 FROM wa_outbox WHERE prospect_id = ? AND kind = 'opener'", (pid,)) and p.get("source") != "self-test":
            report.append(f"{pid} {p['firm']}: opener already queued or sent")
        else:
            store.execute("INSERT INTO wa_outbox (prospect_id, phone, text, kind, created_at) VALUES (?, ?, ?, 'opener', ?)",
                          (pid, mobiles[0], text, iso()))
            report.append(f"{pid} {p['firm']}: queued for {mobiles[0]}")
    return report


def queue_followups(store: Store, after_days: int = 3) -> int:
    cutoff = iso(utcnow() - timedelta(days=after_days))
    rows = store.all(
        "SELECT o.prospect_id, o.phone FROM wa_outbox o WHERE o.kind = 'opener' AND o.status = 'sent' AND o.sent_at <= ? "
        "AND NOT EXISTS (SELECT 1 FROM wa_outbox f WHERE f.prospect_id = o.prospect_id AND f.kind = 'followup') "
        "AND NOT EXISTS (SELECT 1 FROM touches t WHERE t.phone = o.phone AND t.channel = 'whatsapp' AND t.direction = 'in')",
        (cutoff,),
    )
    for r in rows:
        store.execute("INSERT INTO wa_outbox (prospect_id, phone, text, kind, created_at) VALUES (?, ?, ?, 'followup', ?)",
                      (r["prospect_id"], r["phone"], FOLLOW_UP, iso()))
    return len(rows)


async def send_next(store: Store, settings: Settings, gateway: Gateway) -> str | None:
    """Send at most one queued message, if every check passes now. Returns a status line."""
    row = store.one("SELECT * FROM wa_outbox WHERE status = 'queued' ORDER BY id LIMIT 1")
    if not row:
        return None
    prospect = store.prospect(row["prospect_id"])
    decision = can_contact(store, settings, prospect, row["phone"], "whatsapp", check_live=False) if prospect else None
    if decision is None or not decision.ok:
        reasons = decision.reasons if decision is not None else ["prospect missing"]
        if decision is None or any(b in r for r in reasons for b in PERMANENT_BLOCKS):
            store.execute("UPDATE wa_outbox SET status = 'blocked', error = ? WHERE id = ?", ("; ".join(reasons), row["id"]))
            return f"blocked #{row['id']}: {'; '.join(reasons)}"
        return f"waiting: {'; '.join(reasons)}"
    problems = guardrails.check_outbound(row["text"])
    if problems:
        store.execute("UPDATE wa_outbox SET status = 'blocked', error = ? WHERE id = ?", ("; ".join(problems), row["id"]))
        return f"blocked #{row['id']}: {'; '.join(problems)}"
    if gateway.name == "dry":
        return f"[dry run] would send #{row['id']} to {prospect['firm']} {row['phone']}: {row['text']}"
    try:
        if not await gateway.exists(row["phone"]):
            store.execute("UPDATE wa_outbox SET status = 'failed', error = 'not on WhatsApp' WHERE id = ?", (row["id"],))
            return f"#{row['id']} {row['phone']} is not on WhatsApp"
        await gateway.typing(row["phone"], min(8.0, 2.0 + len(row["text"]) / 60))
        await gateway.send(row["phone"], row["text"])
    except httpx.HTTPError as e:
        store.execute("UPDATE wa_outbox SET status = 'failed', error = ? WHERE id = ?", (str(e)[:300], row["id"]))
        return f"#{row['id']} failed: {e}"
    store.execute("UPDATE wa_outbox SET status = 'sent', sent_at = ? WHERE id = ?", (iso(), row["id"]))
    store.log("whatsapp", "out", prospect_id=row["prospect_id"], phone=row["phone"], text=row["text"],
              outcome="sent", meta={"kind": row["kind"], "gateway": gateway.name})
    store.execute("INSERT OR IGNORE INTO wa_chats (phone, prospect_id, updated_at) VALUES (?, ?, ?)",
                  (row["phone"], row["prospect_id"], iso()))
    return f"sent #{row['id']} to {prospect['firm']}"


async def sender_loop(store: Store, settings: Settings, gateway: Gateway, stop: asyncio.Event) -> None:
    """Send queued messages one by one with long random gaps, like a person would."""
    if not settings.live or gateway.name == "dry":
        log.warning("live mode is off: the WhatsApp sender is idle")
        return
    while not stop.is_set():
        status = await send_next(store, settings, gateway)
        if status:
            log.info(status)
        sent = bool(status and status.startswith("sent"))
        wait = random.uniform(settings.wa_min_gap_seconds, settings.wa_max_gap_seconds) if sent else 60
        try:
            await asyncio.wait_for(stop.wait(), timeout=wait)
        except TimeoutError:
            pass


# ---- inbound ---------------------------------------------------------------------
async def handle_inbound(store: Store, llm: LLM, settings: Settings, gateway: Gateway,
                         phone: str, text: str, *, reply_delay: tuple[float, float] = (15, 60)) -> str | None:
    """Reply to a prospect's WhatsApp message. Returns the reply sent, or None."""
    prospect = store.prospect_by_phone(phone)
    if not prospect:
        return None  # not a prospect: never touch personal chats
    chat = store.one("SELECT * FROM wa_chats WHERE phone = ?", (phone,))
    if not chat:
        store.execute("INSERT INTO wa_chats (phone, prospect_id, updated_at) VALUES (?, ?, ?)", (phone, prospect["id"], iso()))
        chat = store.one("SELECT * FROM wa_chats WHERE phone = ?", (phone,))

    convo = Conversation.load(store, llm, prospect, phone, "whatsapp",
                              agent_name=settings.agent_name, agent_gender=settings.agent_gender)
    store.log("whatsapp", "in", prospect_id=prospect["id"], phone=phone, text=text)

    opted_out_before = store.is_suppressed(phone)
    if opted_out_before:
        return None
    if chat["mode"] == "human" and not guardrails.is_opt_out(text):
        await _notify_owner(store, settings, gateway, f"FieldOS sales: new WhatsApp from {prospect['firm']} ({phone}): {text[:300]}")
        return None

    turn = convo.respond(text)
    reply = turn.say
    if turn.outcome != "opted_out" and not chat["ai_disclosed"]:
        reply = reply + "\n\n" + DISCLOSURE["whatsapp"][turn.language]
        store.execute("UPDATE wa_chats SET ai_disclosed = 1 WHERE phone = ?", (phone,))

    if turn.outcome in ("demo_booked", "handover", "callback_later"):
        store.execute("UPDATE wa_chats SET mode = 'human', updated_at = ? WHERE phone = ?", (iso(), phone))
        await _notify_owner(store, settings, gateway,
                            f"FieldOS sales: {prospect['firm']} ({phone}) -> {turn.outcome}. "
                            f"{('Slot: ' + turn.demo_slot + '. ') if turn.demo_slot else ''}{turn.note} The bot has stopped replying in this chat.")

    await asyncio.sleep(random.uniform(*reply_delay))
    await gateway.typing(phone, min(6.0, 1.5 + len(reply) / 70))
    await gateway.send(phone, reply)
    store.log("whatsapp", "out", prospect_id=prospect["id"], phone=phone, text=reply, outcome="reply",
              meta={"turn_outcome": turn.outcome, "gateway": gateway.name, "dry_run": gateway.name == "dry"})
    return reply


async def _notify_owner(store: Store, settings: Settings, gateway: Gateway, text: str) -> None:
    store.log("whatsapp", "alert", text=text, outcome="owner_alert")
    owner = normalise_indian_phone(settings.owner_notify_number) if settings.owner_notify_number else None
    if owner:
        try:
            await gateway.send(owner, text)
        except httpx.HTTPError:
            log.exception("could not alert the owner")


def chat_link(phone: str) -> str:
    return "https://wa.me/" + quote(_digits(phone))
