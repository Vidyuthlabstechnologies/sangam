from datetime import UTC, datetime

import pytest

from fieldos_sales import selftest
from fieldos_sales.compliance import can_contact
from fieldos_sales.insights import compute
from fieldos_sales.llm import OfflineLLM

from .helpers import MOBILE, make

NIGHT_SATURDAY = datetime(2026, 11, 14, 19, 30, tzinfo=UTC)  # 1 am Sunday IST


def test_selftest_needs_number_in_test_numbers():
    s, st = make()
    with pytest.raises(ValueError, match="TEST_NUMBERS"):
        selftest.add(st, s, OfflineLLM(), "9876543210")


def test_selftest_skips_hours_and_dnd_but_not_live_or_optout():
    s, st = make(test_numbers=("+919876543210",))
    pid = selftest.add(st, s, OfflineLLM(), "98765 43210", contact_name="Ravi")
    p = st.prospect(pid)
    assert p["phones"] == ["+919876543210"] and st.draft(pid, "wa_opener")
    assert can_contact(st, s, p, "+919876543210", "call", NIGHT_SATURDAY).ok
    off, _ = make(live=False, test_numbers=("+919876543210",))
    assert "live mode" in can_contact(st, off, p, "+919876543210", "call", NIGHT_SATURDAY).reasons[0]
    st.suppress("+919876543210", "stop")
    assert not can_contact(st, s, p, "+919876543210", "call", NIGHT_SATURDAY).ok
    assert selftest.reset(st) == 1
    assert can_contact(st, s, p, "+919876543210", "call", NIGHT_SATURDAY).ok
    # adding again reuses the same test firm
    assert selftest.add(st, s, OfflineLLM(), "+919876543210") == pid


def test_real_prospects_keep_every_check_and_test_firms_stay_out_of_insights():
    s, st = make(test_numbers=(MOBILE,))  # even if a prospect's number is listed by mistake
    assert not can_contact(st, s, st.prospect(1), MOBILE, "call", NIGHT_SATURDAY).ok
    s2, st2 = make(test_numbers=("+919876543210",))
    pid = selftest.add(st2, s2, OfflineLLM(), "+919876543210")
    st2.log("call", "out", prospect_id=pid, phone="+919876543210", outcome="dialled", meta={"call_sid": "T"})
    data = compute(st2)
    assert data["calls"]["dialled"] == 0 and data["funnel"][0]["n"] == 1
