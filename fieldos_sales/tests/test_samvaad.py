import json

import httpx
import pytest
from fastapi.testclient import TestClient

from fieldos_sales.llm import OfflineLLM
from fieldos_sales.samvaad import (
    SamvaadDialer,
    SamvaadError,
    call_inputs,
    describe,
    handle_webhook,
    make_dial,
)
from fieldos_sales.server import create_app
from fieldos_sales.store import iso
from fieldos_sales.whatsapp import DryGateway

from .helpers import MOBILE, make, ready_for

DEPLOYMENTS = {"items": [
    {"deployment_id": "dep-in", "app_id": "support", "app_version": 1, "phone_numbers": ["+918047160000"],
     "channel_direction": "inbound", "name": "Support"},
    {"deployment_id": "dep-1", "app_id": "fieldos-sales", "app_version": 3, "phone_numbers": ["+918047161111"],
     "channel_direction": "inbound_outbound", "name": "sangam", "status": "active"},
], "next_page_uri": None}
DEPLOYMENT = {"app_id": "fieldos-sales", "app_version": 3, "name": "sangam",
              "connection_configs": [{"connection_id": "conn-9", "agent_phone_number": "+918047161111"}]}


class Fake:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers=None, params=None, json=None):
        self.calls.append((method, url, headers, json))
        req = httpx.Request(method, url)
        if url.endswith("/deployments"):
            return httpx.Response(200, json=DEPLOYMENTS, request=req)
        if url.endswith("/deployments/dep-1"):
            return httpx.Response(200, json=DEPLOYMENT, request=req)
        if url.endswith("/outbounds"):
            return httpx.Response(200, json={"attempt_id": "att-1"}, request=req)
        return httpx.Response(404, text="nope", request=req)


def settings_for(**kw):
    return make(samvaad_api_key="k", samvaad_org_id="org", samvaad_workspace_id="ws", **kw)


def test_finds_the_sangam_line_and_places_a_call_with_the_firms_notes():
    s, st = settings_for(public_base_url="https://x.example", voice_stream_token="vt")
    ready_for(st, "call")
    fake = Fake()
    attempt = make_dial(st, s, SamvaadDialer(s, fake))(MOBILE, 1)
    assert attempt == "att-1"
    method, url, headers, body = fake.calls[-1]
    assert url == "https://apps.sarvam.ai/api/outbounds/v1/orgs/org/workspaces/ws/outbounds" and headers["X-API-Key"] == "k"
    assert body["app_config"]["app_id"] == "fieldos-sales" and body["app_config"]["app_version"] == 3
    assert body["app_config"]["connection_config"] == {"connection_id": "conn-9", "agent_phone_number": "+918047161111"}
    assert body["user_config"] == {"user_phone_number": MOBILE}
    assert body["app_config"]["agent_variables"]["firm_name"] == "Demo Builders"
    opening = body["app_config"]["app_overrides"]["initial_bot_message"]
    assert "FieldOS" in opening and "AI" not in opening and "record" not in opening.lower()
    assert body["webhook_config"]["url"] == "https://x.example/samvaad/webhook?token=vt"


def test_not_configured_and_no_matching_line_fail_clearly():
    s, _ = make()
    with pytest.raises(SamvaadError, match="SARVAM_SAMVAAD_API_KEY"):
        SamvaadDialer(s, Fake()).line()
    s2, _ = settings_for(samvaad_deployment="nothing-like-this")
    with pytest.raises(SamvaadError, match="no outbound deployment"):
        SamvaadDialer(s2, Fake()).line()
    lines = describe(SamvaadDialer(s2, Fake()))
    assert "sangam" in lines[1] and "1111" in lines[1] and "8047161111" not in lines[1]  # numbers masked


def test_pricing_in_the_notes_blocks_the_call():
    s, st = settings_for()
    st.save_draft(1, "call_brief", "Tell them it is only Rs 999 a month")
    st.approve(1, "call")
    with pytest.raises(SamvaadError, match="outbound check"):
        call_inputs(st, s, st.prospect(1), MOBILE)


def _row(st):
    st.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES ('att-1', 1, ?, 'queued', ?)",
               (MOBILE, iso()))


def test_webhook_logs_transcript_outcome_and_opt_out():
    s, st = settings_for(voice_stream_token="vt", auto_summarise=False)
    _row(st)
    client = TestClient(create_app(s, st, OfflineLLM(), DryGateway(), run_sender=False))
    payload = {"attempt_id": "att-1", "status": "connected", "duration": 64.2, "interaction_id": "i1",
               "final_agent_variables": {"call_outcome": "demo_booked", "demo_slot": "Thu 11 am", "language": "hi"},
               "interaction_transcript": [{"role": "agent", "en_text": "Good morning ji!"},
                                          {"role": "user", "en_text": "Yes, tell me. How much does it cost?"},
                                          {"role": "agent", "en_text": "Our team shares a proposal after a walkthrough."}]}
    assert client.post("/samvaad/webhook?token=bad", json=payload).status_code == 403
    out = client.post("/samvaad/webhook?token=vt", json=payload).json()
    assert out["outcome"] == "demo_booked"
    t = st.one("SELECT * FROM touches WHERE direction = 'transcript'")
    meta = json.loads(t["meta"])
    assert meta["prospect_turns"] == 1 and meta["price_asks"] == 1 and "Prospect: Yes" in t["text"]
    assert st.one("SELECT status FROM calls WHERE call_sid = 'att-1'")["status"] == "completed"
    ev = st.one("SELECT meta FROM touches WHERE direction = 'event' AND outcome = 'demo_booked'")
    assert json.loads(ev["meta"])["demo_slot"] == "Thu 11 am"

    st.execute("UPDATE calls SET call_sid = 'att-2'")
    handle_webhook(st, {"attempt_id": "att-2", "status": "connected", "final_agent_variables": {},
                        "interaction_transcript": [{"role": "user", "en_text": "Stop calling me"},
                                                   {"role": "agent", "en_text": "It is only Rs 999 per month"}]})
    assert st.is_suppressed(MOBILE)
    assert st.one("SELECT 1 FROM touches WHERE outcome = 'pricing_alert'")


def test_unanswered_call_is_logged_as_status():
    s, st = settings_for()
    _row(st)
    assert handle_webhook(st, {"attempt_id": "att-1", "status": "no_answer"})["logged"] == "status"
    assert st.one("SELECT status FROM calls")["status"] == "no_answer"
    assert handle_webhook(st, {"attempt_id": "zzz", "status": "busy"})["ok"] is False
