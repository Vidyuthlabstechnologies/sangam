"""Test the agents on your own phone before any prospect.

`selftest add` creates a pretend firm whose number is yours (it must be listed in TEST_NUMBERS),
writes its drafts and approves it. For these test firms only, the contact-hours, DND-scrub,
call-frequency and daily-cap checks are skipped, so you can test at any time and as often as
you like. Live mode, the pricing filter, the honest answer to "are you a bot?" and opt-out handling all still apply.
Test firms are left out of the insights dashboard. `selftest reset` clears their history
(including a STOP you sent while testing) so you can run the test again.
"""
from __future__ import annotations

from .config import Settings
from .llm import LLM
from .pitch import write_pitch
from .prospects import normalise_indian_phone
from .store import Store

SOURCE = "self-test"
FIRST_ID = 9001


def is_test(settings: Settings, prospect: dict | None, phone: str) -> bool:
    return bool(prospect) and prospect.get("source") == SOURCE and phone in settings.test_numbers


def test_ids(store: Store) -> set[int]:
    return {r["id"] for r in store.all("SELECT id FROM prospects WHERE source = ?", (SOURCE,))}


DEFAULT_PROFILE = {
    "summary": "A mid-size Hyderabad builder running 4 apartment sites at once, with site supervisors reporting by WhatsApp and paper registers.",
    "business_type": "residential developer and contractor",
    "project_types": ["gated villa community", "G+5 apartments"],
    "locations": ["Kokapet", "Tellapur"],
    "scale_signals": ["4 sites running", "about 120 workers"],
    "likely_pains": ["Saturday wage disputes and advances paid twice", "cement and steel short deliveries", "owner can't see every site daily"],
    "fieldos_fits": [{"pain": "wage disputes", "feature": "Weekly wage sheet with advances", "why": "wages come from attendance with advances recorded"},
                     {"pain": "no daily view", "feature": "Daily Site Brief", "why": "one screen shows which site needs attention"}],
    "opening_hook": "your villa project in Kokapet",
    "decision_maker_hint": "the managing partner", "language_hint": "en", "confidence": "high", "evidence": [],
    "sources": ["self-test (made up)"],
}


def add(store: Store, settings: Settings, llm: LLM, phone: str, firm: str = "Test Builders (you)",
        contact_name: str = "", language: str = "en", segment: str = "Developer") -> int:
    number = normalise_indian_phone(phone)
    if not number:
        raise ValueError(f"not a valid Indian number: {phone}")
    if number not in settings.test_numbers:
        raise ValueError(f"{number} is not in TEST_NUMBERS in .env; add it there first (only your own numbers)")
    existing = store.one("SELECT id FROM prospects WHERE source = ? AND phones LIKE ?", (SOURCE, f'%"{number}"%'))
    pid = existing["id"] if existing else max(FIRST_ID - 1, *(test_ids(store) or {0})) + 1
    store.upsert_prospect({"id": pid, "firm": firm, "segment": segment, "size": "Mid", "priority": "T - self test",
                           "phones": [number], "source": SOURCE, "contact_name": contact_name,
                           "owner_notes": "Self-test prospect: this is the owner's own phone."})
    store.execute("UPDATE prospects SET language = ? WHERE id = ?", (language if language in ("en", "hi", "te") else "en", pid))
    profile = {**DEFAULT_PROFILE, "language_hint": language}
    store.save_profile(pid, profile)
    out = write_pitch(store.prospect(pid), profile, llm)
    store.save_draft(pid, "call_brief", out["call_brief"])
    store.save_draft(pid, "wa_opener", out["whatsapp_opener"])
    store.approve(pid, "call")
    store.approve(pid, "whatsapp")
    return pid


def reset(store: Store) -> int:
    ids = test_ids(store)
    for pid in ids:
        p = store.prospect(pid)
        for phone in p["phones"] if p else []:
            store.execute("DELETE FROM suppressions WHERE phone = ?", (phone,))
            store.execute("DELETE FROM wa_chats WHERE phone = ?", (phone,))
        store.execute("DELETE FROM touches WHERE prospect_id = ?", (pid,))
        store.execute("DELETE FROM wa_outbox WHERE prospect_id = ?", (pid,))
        store.execute("DELETE FROM calls WHERE prospect_id = ?", (pid,))
        store.execute("DELETE FROM call_insights WHERE prospect_id = ?", (pid,))
        store.approve(pid, "call")
        store.approve(pid, "whatsapp")
    return len(ids)
