from types import SimpleNamespace

from fieldos_sales.config import Settings
from fieldos_sales.conversation import Conversation
from fieldos_sales.knowledge import PRICE_DEFLECTION
from fieldos_sales.llm import ClaudeLLM, OfflineLLM
from fieldos_sales.store import Store

from .helpers import MOBILE, make


def convo(responder=None, channel="call"):
    s, st = make()
    st.save_profile(1, {"summary": "Builds G+5 apartments in Kondapur", "opening_hook": "your Kondapur towers",
                        "language_hint": "en", "confidence": "high"})
    llm = OfflineLLM(responder)
    return st, llm, Conversation.load(st, llm, st.prospect(1), MOBILE, channel)


def test_opening_sounds_like_a_person():
    _, _, c = convo()
    text = c.opening()
    assert "AI" not in text and "assistant" not in text and "record" not in text and "Kondapur" in text


def test_opt_out_ends_and_suppresses_without_model():
    st, llm, c = convo()
    c.opening()
    turn = c.respond("Please don't call me again")
    assert turn.end and turn.outcome == "opted_out"
    assert st.is_suppressed(MOBILE)
    assert llm.calls == []


def test_price_question_is_deflected_without_model_then_handed_over():
    _, llm, c = convo()
    assert c.respond("How much does it cost?").say == PRICE_DEFLECTION["en"]
    second = c.respond("Just tell me the price per user")
    assert second.outcome == "handover"
    assert llm.calls == []


def test_admits_being_ai():
    _, _, c = convo()
    assert "virtual assistant, not a person" in c.respond("Are you a robot?").say


def test_model_reply_that_leaks_price_is_regenerated():
    replies = iter([
        {"say": "It is only 999 rupees a month!", "action": "continue", "language": "en", "demo_slot": "", "callback_time": "", "note": ""},
        {"say": "Could I show you a 30-minute walkthrough this week?", "action": "continue", "language": "en", "demo_slot": "", "callback_time": "", "note": ""},
    ])
    _, llm, c = convo(lambda *a: next(replies))
    turn = c.respond("Tell me what it does")
    assert turn.say == "Could I show you a 30-minute walkthrough this week?"
    assert len(llm.calls) == 2


def test_model_that_keeps_leaking_gets_safe_line():
    bad = {"say": "Free for 3 days, then cheap.", "action": "continue", "language": "en", "demo_slot": "", "callback_time": "", "note": ""}
    _, _, c = convo(lambda *a: bad)
    turn = c.respond("Tell me what it does")
    assert "walkthrough" in turn.say and "free" not in turn.say.lower()


def test_model_cannot_claim_to_be_human():
    replies = iter([
        {"say": "I'm a real person from the team.", "action": "continue", "language": "en", "demo_slot": "", "callback_time": "", "note": ""},
        {"say": "I'm the FieldOS AI assistant.", "action": "continue", "language": "en", "demo_slot": "", "callback_time": "", "note": ""},
    ])
    _, _, c = convo(lambda *a: next(replies))
    assert c.respond("who are you exactly").say == "I'm the FieldOS AI assistant."


def test_demo_booking_is_logged():
    st, _, c = convo(lambda *a: {"say": "Thank you, see you Tuesday at 11.", "action": "book_demo", "language": "en",
                                 "demo_slot": "Tue 11am", "callback_time": "", "note": "Owner, 6 sites"})
    turn = c.respond("Okay come on Tuesday 11 am")
    assert turn.outcome == "demo_booked" and turn.end
    assert st.one("SELECT outcome FROM touches WHERE outcome = 'demo_booked'")


def test_language_switch_to_telugu_uses_telugu_lines():
    _, _, c = convo()
    c.language = "te"
    assert c.respond("vaddu").say.startswith("సరే అండి")


def test_opening_is_natural_and_uses_name_and_time():
    st, llm, c = convo()
    st.execute("UPDATE prospects SET contact_name = 'Ramesh Rao' WHERE id = 1")
    c = Conversation.load(st, llm, st.prospect(1), MOBILE, "call", agent_name="Priya")
    from datetime import UTC, datetime
    text = c.opening(now=datetime(2026, 11, 10, 4, 0, tzinfo=UTC))  # 9:30 IST
    assert text.startswith("Good morning Ramesh ji! Priya here, from FieldOS")
    assert "I saw your Kondapur towers" in text


def test_hindi_opening_respects_agent_gender():
    st, llm, _ = convo()
    st.save_profile(1, {"language_hint": "hi"})
    female = Conversation.load(st, llm, st.prospect(1), MOBILE, "call", agent_name="Priya").opening()
    male = Conversation.load(st, llm, st.prospect(1), MOBILE, "call", agent_name="Arjun", agent_gender="m").opening()
    assert "बोल रही" in female and "AI" not in female
    assert "बोल रहा" in male and "Arjun" in male


def test_backchannel_never_repeats_twice_in_a_row():
    _, _, c = convo()
    said = [c.backchannel() for _ in range(30)]
    assert all(a != b for a, b in zip(said, said[1:], strict=False))


def test_send_info_outcome():
    st, _, c = convo(lambda *a: {"say": "Sure, I'll send a one-minute video on WhatsApp.", "action": "send_info",
                                 "language": "en", "demo_slot": "", "callback_time": "", "note": "wants video"})
    assert c.respond("just send me details on whatsapp").outcome == "send_info"


def test_claude_request_shape_for_live_calls():
    """Live calls ask Haiku for a fast answer: thinking off, low effort, JSON schema, spend recorded."""
    sent = {}

    class FakeMessages:
        def create(self, **kwargs):
            sent.update(kwargs)
            return SimpleNamespace(
                stop_reason="end_turn",
                usage=SimpleNamespace(input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0),
                content=[SimpleNamespace(type="text", text='{"ok": true}')],
            )

    st = Store(":memory:")
    llm = ClaudeLLM(Settings(model="claude-haiku-5-5"), st, client=SimpleNamespace(messages=FakeMessages()))
    out = llm.json(purpose="call_turn", system=[{"type": "text", "text": "x"}],
                   messages=[{"role": "user", "content": "hi"}], schema={"type": "object"}, fast=True)
    assert out == {"ok": True}
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["thinking"] == {"type": "disabled"}
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert 0 < st.llm_spend_today() < 0.001


def test_budget_cap_hands_over():
    s, st = make(llm_daily_budget_usd=0.01)
    st.add_llm_usage("x", 0, 0, 0.02)
    llm = ClaudeLLM(s, st, client=SimpleNamespace(messages=None))
    c = Conversation.load(st, llm, st.prospect(1), MOBILE, "call")
    assert c.respond("tell me more").action == "handover"
