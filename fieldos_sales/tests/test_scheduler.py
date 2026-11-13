from datetime import UTC, date, datetime

from fieldos_sales.scheduler import cancel_all, dial_due, plan_calls

from .helpers import MOBILE, WORK_HOURS, make, ready_for


def test_plan_spreads_calls_over_weekdays_in_good_hours():
    s, st = make(calls_per_day=3)
    for i in range(2, 8):
        st.upsert_prospect({"id": i, "firm": f"F{i}", "priority": "A" if i % 2 else "B", "phones": [f"+9191000508{i:02d}"]})
    planned = plan_calls(st, s, st.prospects(), start=date(2026, 11, 13))  # a Friday
    assert len(planned) == 7
    days = {p["slot"].date() for p in planned}
    assert date(2026, 11, 14) not in days and date(2026, 11, 15) not in days  # no Saturday/Sunday calls
    assert all((11 <= p["slot"].hour < 13) or (15 <= p["slot"].hour < 18) for p in planned)
    assert planned[0]["firm"] in ("F3", "F5", "F7", "Demo Builders")  # priority A first
    assert plan_calls(st, s, st.prospects()) == []  # already scheduled
    assert cancel_all(st) == 7


def test_due_call_dials_only_when_every_check_passes():
    s, st = make()
    plan_calls(st, s, [st.prospect(1)], start=date(2026, 11, 10))
    dialled = []
    out = dial_due(st, s, lambda phone, pid: dialled.append(phone) or "CA1", now=datetime(2026, 11, 10, 12, 0, tzinfo=UTC))
    assert not dialled and "skipped" in out[0] and "not approved" in out[0]

    s, st = make()
    ready_for(st, "call")
    plan_calls(st, s, [st.prospect(1)], start=date(2026, 11, 10))
    out = dial_due(st, s, lambda phone, pid: dialled.append(phone) or "CA1", now=datetime(2026, 11, 10, 12, 0, tzinfo=UTC))
    assert dialled == [MOBILE] and out[0].startswith("dialled")
    assert st.one("SELECT 1 FROM calls WHERE call_sid = 'CA1'")


def test_due_call_outside_hours_moves_to_next_slot():
    s, st = make()
    ready_for(st, "call")
    plan_calls(st, s, [st.prospect(1)], start=date(2026, 11, 10))
    out = dial_due(st, s, lambda *a: "X", now=datetime(2026, 11, 10, 14, 0, tzinfo=UTC))  # 19:30 IST
    assert out[0].startswith("moved") and "Wed 11 Nov 11:00" in out[0]
    assert WORK_HOURS
