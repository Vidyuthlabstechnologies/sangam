from datetime import timedelta

from fieldos_sales.compliance import can_contact, import_dnd_csv
from fieldos_sales.prospects import normalise_indian_phone, split_phones

from .helpers import LANDLINE, MOBILE, WORK_HOURS, make, ready_for


def test_everything_in_place_allows_call():
    s, st = make()
    ready_for(st, "call")
    d = can_contact(st, s, st.prospect(1), MOBILE, "call", WORK_HOURS)
    assert d.ok, d.reasons


def test_live_switch_off_blocks():
    s, st = make(live=False)
    ready_for(st, "call")
    d = can_contact(st, s, st.prospect(1), MOBILE, "call", WORK_HOURS)
    assert not d.ok and any("live mode" in r for r in d.reasons)


def test_needs_owner_approval():
    s, st = make()
    st.set_dnd(MOBILE, False, WORK_HOURS)
    d = can_contact(st, s, st.prospect(1), MOBILE, "call", WORK_HOURS)
    assert any("not approved" in r for r in d.reasons)


def test_new_draft_clears_approval():
    s, st = make()
    ready_for(st, "whatsapp")
    st.save_draft(1, "wa_opener", "edited text")
    assert not st.is_approved(1, "whatsapp")


def test_call_needs_fresh_dnd_scrub():
    s, st = make()
    st.save_draft(1, "call_brief", "x")
    st.approve(1, "call")
    d = can_contact(st, s, st.prospect(1), MOBILE, "call", WORK_HOURS)
    assert any("no DND scrub" in r for r in d.reasons)
    st.set_dnd(MOBILE, False, WORK_HOURS - timedelta(days=30))
    d = can_contact(st, s, st.prospect(1), MOBILE, "call", WORK_HOURS)
    assert any("older than" in r for r in d.reasons)


def test_dnd_registered_blocks_every_channel():
    s, st = make()
    ready_for(st, "whatsapp")
    st.set_dnd(MOBILE, True, WORK_HOURS)
    assert not can_contact(st, s, st.prospect(1), MOBILE, "whatsapp", WORK_HOURS).ok


def test_opt_out_blocks_and_cancels_queue():
    s, st = make()
    ready_for(st, "whatsapp")
    st.execute("INSERT INTO wa_outbox (prospect_id, phone, text, created_at) VALUES (1, ?, 'hi', '2026-11-10')", (MOBILE,))
    st.suppress(MOBILE, "asked to stop")
    d = can_contact(st, s, st.prospect(1), MOBILE, "whatsapp", WORK_HOURS)
    assert any("opted out" in r for r in d.reasons)
    assert st.one("SELECT status FROM wa_outbox")["status"] == "blocked"


def test_night_and_sunday_blocked():
    s, st = make()
    ready_for(st, "call")
    night = WORK_HOURS.replace(hour=16)  # 21:30 IST
    sunday = WORK_HOURS + timedelta(days=5)
    assert any("contact hours" in r for r in can_contact(st, s, st.prospect(1), MOBILE, "call", night).reasons)
    assert any("contact hours" in r for r in can_contact(st, s, st.prospect(1), MOBILE, "call", sunday).reasons)


def test_whatsapp_needs_a_mobile():
    s, st = make()
    ready_for(st, "whatsapp", LANDLINE)
    d = can_contact(st, s, st.prospect(1), LANDLINE, "whatsapp", WORK_HOURS)
    assert any("mobile" in r for r in d.reasons)


def test_call_frequency_and_daily_cap():
    s, st = make(calls_per_day=1)
    ready_for(st, "call")
    st.log("call", "out", prospect_id=1, phone=MOBILE, outcome="dialled")
    d = can_contact(st, s, st.prospect(1), MOBILE, "call")
    assert any("last 7 days" in r for r in d.reasons)
    assert any("daily call cap" in r for r in d.reasons)


def test_whatsapp_stops_after_two_unanswered():
    s, st = make()
    ready_for(st, "whatsapp")
    for _ in range(2):
        st.log("whatsapp", "out", prospect_id=1, phone=MOBILE, outcome="sent")
    d = can_contact(st, s, st.prospect(1), MOBILE, "whatsapp", WORK_HOURS)
    assert any("no reply" in r for r in d.reasons)
    st.log("whatsapp", "in", prospect_id=1, phone=MOBILE, text="tell me more")
    assert can_contact(st, s, st.prospect(1), MOBILE, "whatsapp", WORK_HOURS).ok


def test_number_must_belong_to_prospect():
    s, st = make()
    ready_for(st, "call", "+919999999999")
    d = can_contact(st, s, st.prospect(1), "+919999999999", "call", WORK_HOURS)
    assert any("does not belong" in r for r in d.reasons)


def test_dnd_csv_import(tmp_path):
    s, st = make()
    f = tmp_path / "scrub.csv"
    f.write_text("phone,dnd\n091000 50801,no\n+91 40 2341 8080,yes\nbad,maybe\n")
    total, registered = import_dnd_csv(st, f)
    assert (total, registered) == (2, 1)
    assert st.dnd(LANDLINE)["registered"] == 1


def test_phone_normalisation():
    assert normalise_indian_phone("+91 77028 39622") == "+917702839622"
    assert normalise_indian_phone("040-23418080") == "+914023418080"
    assert normalise_indian_phone("12345") is None
    assert split_phones("+91 91000 50801, +91 80295 35801") == ["+919100050801", "+918029535801"]
