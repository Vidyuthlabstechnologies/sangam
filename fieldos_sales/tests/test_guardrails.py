import pytest

from fieldos_sales import guardrails
from fieldos_sales.conversation import (
    AI_ANSWER,
    DISCLOSURE,
    GOODBYE_OPT_OUT,
    HANDOVER,
    SAFE_LINE,
)
from fieldos_sales.knowledge import KNOWLEDGE_TEXT, PRICE_DEFLECTION
from fieldos_sales.pitch import fallback_opener
from fieldos_sales.whatsapp import FOLLOW_UP


@pytest.mark.parametrize("text", [
    "It is ₹999 a month per person.",
    "Only Rs 2,49,000 a year for three sites.",
    "Plans start at 49k for the pilot.",
    "We charge per site, unlimited users.",
    "You get a 3-day free trial.",
    "It's much cheaper than Onsite.",
    "We can give 25% off for founding customers.",
    "The annual subscription includes onboarding.",
    "It costs less than one worker's daily wage.",
    "Sirf 999 rupaye mahina.",
    "यह मुफ्त है",
    "ఇది ఉచితం",
    "The paid pilot runs for 60 days.",
    "1,49,000 for the year",
    "Ek lakh se kam",
    "2 lakh only",
])
def test_pricing_is_blocked(text):
    assert guardrails.pricing_violation(text), text


@pytest.mark.parametrize("text", [
    "Supervisors punch in a whole gang in one tap, even with no signal.",
    "Could I show you a 30-minute walkthrough this week?",
    "The PO shows 380 of 400 bags received and 20 still to come.",
    "Advances were paid twice at one of your sites?",
    "How many sites are you running right now, sir?",
])
def test_normal_sales_talk_is_allowed(text):
    assert guardrails.pricing_violation(text) is None, text


def test_every_fixed_line_we_send_passes_the_checks():
    lines = [fallback_opener({"firm": "Demo Builders"}), FOLLOW_UP]
    for table in (PRICE_DEFLECTION, AI_ANSWER, HANDOVER, SAFE_LINE):
        lines += list(table.values())
    for table in (DISCLOSURE, GOODBYE_OPT_OUT):
        for per_lang in table.values():
            lines += [v.format(hook="") for v in per_lang.values()]
    for line in lines:
        assert guardrails.check_outbound(line) == [], line


def test_knowledge_base_has_no_pricing():
    for line in KNOWLEDGE_TEXT.splitlines():
        assert guardrails.pricing_violation(line) is None, line


@pytest.mark.parametrize("text", [
    "I am a real person, not a bot.", "I'm not an AI", "main insaan hoon", "I am human",
])
def test_human_claims_blocked(text):
    assert guardrails.claims_human(text)


@pytest.mark.parametrize("text", [
    "STOP", "stop", "Please don't call me again", "not interested", "remove my number",
    "call mat karo", "band karo", "nahi chahiye", "मुझे कॉल मत करो", "vaddu", "ఆపండి", "No more messages please",
    "do not contact us", "this is spam",
])
def test_opt_out_detected(text):
    assert guardrails.is_opt_out(text), text


@pytest.mark.parametrize("text", [
    "Yes tell me", "We are running 4 sites", "I'm busy now, call tomorrow", "Who is this?", "ok",
    "Can you stop by our office on Tuesday?",
])
def test_not_opt_out(text):
    assert not guardrails.is_opt_out(text), text


@pytest.mark.parametrize("text", ["How much does it cost?", "kitna paisa lagega", "What are the charges?", "ఎంత అవుతుంది", "is there a free trial"])
def test_price_questions_detected(text):
    assert guardrails.asks_about_price(text)


@pytest.mark.parametrize("text", ["We plan to start a new tower", "I'm free on Tuesday", "Send me the details"])
def test_not_price_questions(text):
    assert not guardrails.asks_about_price(text)


@pytest.mark.parametrize("text", ["Are you a robot?", "is this a recording", "kya aap robot ho", "are you human"])
def test_asks_if_ai(text):
    assert guardrails.asks_if_ai(text)
