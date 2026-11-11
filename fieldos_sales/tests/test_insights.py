import base64
import json
import struct

from fastapi.testclient import TestClient

from fieldos_sales.audio import RATE
from fieldos_sales.dashboard import render
from fieldos_sales.insights import (
    SUMMARY_SCHEMA,
    compute,
    learn,
    summarise_pending,
    text_report,
)
from fieldos_sales.llm import OfflineLLM
from fieldos_sales.sample import build
from fieldos_sales.server import create_app
from fieldos_sales.store import Store
from fieldos_sales.whatsapp import DryGateway

from .helpers import MOBILE, make

TURN = {"say": "How do your supervisors send attendance today, sir?", "action": "continue", "language": "en",
        "demo_slot": "", "callback_time": "", "note": ""}
SUMMARY = {"summary": "Owner runs 4 sites, uses a register.", "interest": "hot", "sentiment": "positive",
           "decision_maker": "yes", "current_method": "Paper register", "competitors": ["Onsite"],
           "pains": ["Labour attendance disputes"], "objections": ["no_time"], "why_ended": "booked_demo",
           "next_step": "Confirm Thursday", "agent_mistakes": [], "coaching_tip": "Ask about sites earlier."}


def responder(purpose, messages, schema):
    if purpose == "insight_summary":
        return SUMMARY
    if purpose == "insight_learn":
        return {"headline": "h", "what_works": ["a"], "what_hurts": ["b"],
                "changes": [{"change": "c", "why": "d", "area": "opening"}]}
    return TURN


def test_summary_schema_is_strict():
    assert SUMMARY_SCHEMA["additionalProperties"] is False
    assert set(SUMMARY_SCHEMA["required"]) == set(SUMMARY_SCHEMA["properties"])


def test_empty_database_computes():
    _, st = make()
    data = compute(st)
    assert data["funnel"][0]["n"] == 1
    assert data["calls"]["dialled"] == 0 and data["calls"]["answer_rate"] is None
    assert "Contacted 0" in text_report(data)


def test_call_and_chat_are_summarised_counted_and_learned_from():
    s, st = make()
    st.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES ('CA1', 1, ?, 'completed', 'x')", (MOBILE,))
    st.log("call", "out", prospect_id=1, phone=MOBILE, outcome="dialled", meta={"call_sid": "CA1"})
    st.log("call", "transcript", prospect_id=1, phone=MOBILE, text="AI: Hello\nProspect: Haan\nAI: Sites?\nProspect: 4",
           outcome="demo_booked", meta={"call_sid": "CA1", "duration_s": 80, "prospect_turns": 2, "latency_ms_avg": 1400,
                                        "language": "hi", "ended_by": "agent", "price_asks": 1})
    st.log("call", "event", prospect_id=1, phone=MOBILE, outcome="demo_booked", meta={"demo_slot": "Thu 4pm", "note": ""})
    st.log("whatsapp", "in", prospect_id=1, phone=MOBILE, text="Tell me more")
    llm = OfflineLLM(responder)
    assert summarise_pending(st, llm) == 2
    assert summarise_pending(st, llm) == 0  # nothing new
    data = compute(st)
    assert data["calls"]["answer_rate"] == 100.0
    assert data["calls"]["price_question_rate"] == 100.0
    assert data["headline"]["demos"] == 1
    assert data["actions"][0]["when"] == "Thu 4pm"
    assert {"name": "no_time", "n": 2} in data["voice"]["objections"]
    assert data["voice"]["current_method"][0]["name"] == "paper register"
    assert data["languages"][0]["name"] == "Hindi"
    assert data["best_times"] and data["best_times"][0]["dialled"] == 1
    learn(st, llm)
    assert compute(st)["learnings"]["headline"] == "h"
    # learn() and summaries must never be asked to reveal pricing
    assert any("Never recommend revealing" in c["system"][0]["text"] for c in llm.calls if c["purpose"] == "insight_learn")


def test_dashboard_escapes_prospect_text():
    _, st = make()
    st.log("call", "transcript", prospect_id=1, phone=MOBILE, text="Prospect: </script><script>alert(1)</script>",
           outcome="ended", meta={"prospect_turns": 1})
    html = render(compute(st))
    assert "</script><script>alert(1)" not in html
    assert html.count("</script>") == 2  # only our own two script tags


def test_sample_data_is_flagged():
    st = Store(":memory:")
    build(st)
    data = compute(st)
    assert data["sample"] is True
    assert all(c["firm"].startswith("Sample firm") for c in data["conversations"])
    assert data["calls"]["dialled"] > 20 and data["voice"]["summarised"] > 10


def test_dashboard_needs_its_token():
    s, st = make(dashboard_token="dash")
    client = TestClient(create_app(s, st, OfflineLLM(responder), DryGateway(), run_sender=False))
    assert client.get("/dashboard").status_code == 403
    assert client.get("/api/insights?token=nope").status_code == 403
    page = client.get("/dashboard?token=dash")
    assert page.status_code == 200 and "FieldOS sales insights" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert client.get("/api/insights?token=dash").json()["funnel"][0]["n"] == 1
    s2, st2 = make()  # no token configured: closed
    assert TestClient(create_app(s2, st2, OfflineLLM(responder), DryGateway(), run_sender=False)).get("/dashboard").status_code == 403


class FakeSpeech:
    def __init__(self, heard):
        self.heard = list(heard)

    async def transcribe(self, pcm):
        from fieldos_sales.telephony import Heard
        return Heard(self.heard.pop(0), "en")

    async def speak(self, text, language="en"):
        return b"\x10\x00" * 320


def test_finished_call_records_metrics_and_gets_summarised():
    s, st = make(voice_stream_token="vt")
    st.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES ('CA9', 1, ?, 'queued', 'x')", (MOBILE,))
    client = TestClient(create_app(s, st, OfflineLLM(responder), DryGateway(), FakeSpeech(["Yes", "Stop calling me"]), run_sender=False))
    n = RATE * 600 // 1000
    audio = base64.b64encode(struct.pack(f"<{n}h", *([3000, -3000] * (n // 2))) + b"\x00\x00" * (RATE * 900 // 1000)).decode()
    with client.websocket_connect("/exotel/stream?token=vt") as ws:
        ws.send_text(json.dumps({"event": "start", "start": {"stream_sid": "S", "call_sid": "CA9"}}))
        ws.send_text(json.dumps({"event": "media", "media": {"payload": audio}}))
        ws.send_text(json.dumps({"event": "media", "media": {"payload": audio}}))
        try:
            while True:
                ws.receive_text()
        except Exception:
            pass
    row = st.one("SELECT * FROM touches WHERE direction = 'transcript'")
    meta = json.loads(row["meta"])
    assert meta["call_sid"] == "CA9" and meta["prospect_turns"] == 2 and meta["ended_by"] == "agent"
    assert meta["latency_ms_avg"] >= s.end_of_turn_ms
    assert st.one("SELECT 1 FROM call_insights WHERE key = ?", (f"call:{row['id']}",))
