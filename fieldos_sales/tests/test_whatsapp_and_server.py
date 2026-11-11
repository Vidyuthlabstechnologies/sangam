import asyncio
import base64
import json
import struct

from fastapi.testclient import TestClient

from fieldos_sales.audio import RATE, UtteranceDetector, pcm_to_wav, wav_to_pcm
from fieldos_sales.llm import OfflineLLM
from fieldos_sales.server import create_app
from fieldos_sales.telephony import Heard
from fieldos_sales.whatsapp import (
    DryGateway,
    handle_inbound,
    parse_waha_event,
    queue_followups,
    queue_openers,
    send_next,
    twilio_signature_ok,
)

from .helpers import MOBILE, WORK_HOURS, make, ready_for

TURN = {"say": "How do your supervisors send attendance today, sir?", "action": "continue", "language": "en",
        "demo_slot": "", "callback_time": "", "note": ""}


class RecordingGateway(DryGateway):
    name = "recording"


def run(coro):
    return asyncio.run(coro)


def test_outbox_sends_only_approved_and_checked(monkeypatch):
    s, st = make()
    st.save_draft(1, "wa_opener", "Namaste from FieldOS. Reply STOP and we won't message again.")
    assert "not approved" in queue_openers(st, [1])[0]
    st.approve(1, "whatsapp")
    assert "queued" in queue_openers(st, [1])[0]
    assert "already" in queue_openers(st, [1])[0]

    gw = RecordingGateway()
    monkeypatch.setattr("fieldos_sales.compliance.utcnow", lambda: WORK_HOURS)
    status = run(send_next(st, s, gw))
    assert status.startswith("sent"), status
    assert gw.sent == [(MOBILE, "Namaste from FieldOS. Reply STOP and we won't message again.")]


def test_dry_gateway_never_marks_sent(monkeypatch):
    s, st = make(live=False)
    ready_for(st, "whatsapp")
    queue_openers(st, [1])
    monkeypatch.setattr("fieldos_sales.compliance.utcnow", lambda: WORK_HOURS)
    assert run(send_next(st, s, DryGateway())).startswith("[dry run]")
    assert st.one("SELECT status FROM wa_outbox")["status"] == "queued"


def test_outbox_waits_outside_hours_and_blocks_after_opt_out(monkeypatch):
    s, st = make()
    ready_for(st, "whatsapp")
    queue_openers(st, [1])
    monkeypatch.setattr("fieldos_sales.compliance.utcnow", lambda: WORK_HOURS.replace(hour=17))
    assert run(send_next(st, s, RecordingGateway())).startswith("waiting")
    st.suppress(MOBILE, "stop")
    assert st.one("SELECT status FROM wa_outbox")["status"] == "blocked"


def test_outbox_rejects_draft_with_pricing():
    s, st = make()
    st.save_draft(1, "wa_opener", "Only ₹999 per month!")
    st.approve(1, "whatsapp")
    assert "pricing" in queue_openers(st, [1])[0]


def test_inbound_reply_discloses_ai_once_and_ignores_strangers():
    s, st = make()
    gw = RecordingGateway()
    llm = OfflineLLM(lambda *a: TURN)
    assert run(handle_inbound(st, llm, s, gw, "+919876543210", "hello", reply_delay=(0, 0))) is None
    first = run(handle_inbound(st, llm, s, gw, MOBILE, "Tell me more", reply_delay=(0, 0)))
    assert "AI assistant" in first
    second = run(handle_inbound(st, llm, s, gw, MOBILE, "We have 5 sites", reply_delay=(0, 0)))
    assert "AI assistant" not in second


def test_inbound_opt_out_confirms_once_then_silence():
    s, st = make()
    gw = RecordingGateway()
    llm = OfflineLLM(lambda *a: TURN)
    reply = run(handle_inbound(st, llm, s, gw, MOBILE, "STOP", reply_delay=(0, 0)))
    assert "won't get any more messages" in reply
    assert st.is_suppressed(MOBILE)
    assert run(handle_inbound(st, llm, s, gw, MOBILE, "hello?", reply_delay=(0, 0))) is None


def test_demo_booking_hands_chat_to_a_person_and_alerts_owner():
    s, st = make(owner_notify_number="9000000000")
    gw = RecordingGateway()
    llm = OfflineLLM(lambda *a: {**TURN, "action": "book_demo", "demo_slot": "Thu 4pm", "say": "Thank you sir, Thursday 4 pm it is."})
    run(handle_inbound(st, llm, s, gw, MOBILE, "Come Thursday 4pm", reply_delay=(0, 0)))
    assert any(p == "+919000000000" and "Thu 4pm" in t for p, t in gw.sent)
    assert st.one("SELECT mode FROM wa_chats WHERE phone = ?", (MOBILE,))["mode"] == "human"
    n = len(gw.sent)
    assert run(handle_inbound(st, llm, s, gw, MOBILE, "Also bring brochure", reply_delay=(0, 0))) is None
    assert len(gw.sent) == n + 1  # only the owner alert


def test_followups_only_without_reply():
    s, st = make()
    st.execute("INSERT INTO wa_outbox (prospect_id, phone, text, kind, status, created_at, sent_at) VALUES (1, ?, 'hi', 'opener', 'sent', '2026-11-01', '2026-11-01T06:00:00+00:00')", (MOBILE,))
    assert queue_followups(st) == 1
    assert queue_followups(st) == 0


def test_waha_event_parsing():
    assert parse_waha_event({"event": "message", "payload": {"from": "919100050801@c.us", "body": "Hi", "fromMe": False}}) == (MOBILE, "Hi")
    assert parse_waha_event({"event": "message", "payload": {"from": "1203@g.us", "body": "group"}}) is None
    assert parse_waha_event({"event": "message", "payload": {"from": "919100050801@c.us", "body": "x", "fromMe": True}}) is None


def test_twilio_signature():
    import base64 as b64
    import hashlib
    import hmac
    url, params = "https://example.test/wa/twilio", {"Body": "hi", "From": "whatsapp:+919100050801"}
    good = b64.b64encode(hmac.new(b"tok", (url + "BodyhiFromwhatsapp:+919100050801").encode(), hashlib.sha1).digest()).decode()
    assert twilio_signature_ok("tok", url, params, good)
    assert not twilio_signature_ok("tok", url, params, "bad")


def test_webhook_needs_token():
    s, st = make(wa_webhook_token="secret")
    client = TestClient(create_app(s, st, OfflineLLM(lambda *a: TURN), RecordingGateway(), run_sender=False))
    assert client.post("/wa/waha?token=wrong", json={}).status_code == 403
    assert client.post("/wa/waha?token=secret", json={"event": "session.status"}).status_code == 200


# ---- voice ------------------------------------------------------------------------
def tone(ms, amp=3000):
    n = RATE * ms // 1000
    return struct.pack(f"<{n}h", *([amp, -amp] * (n // 2)))


def silence(ms):
    return b"\x00\x00" * (RATE * ms // 1000)


def test_utterance_detector():
    d = UtteranceDetector()
    assert d.feed(tone(600)) == []
    out = d.feed(silence(900))
    assert len(out) == 1
    assert d.feed(tone(100) + silence(900)) == []  # too short to count


def test_wav_roundtrip_with_resample():
    pcm16k = tone(500)
    back = wav_to_pcm(pcm_to_wav(pcm16k, rate=16000), RATE)
    assert abs(len(back) - len(pcm16k) // 2) <= 2


class FakeSpeech:
    def __init__(self, heard):
        self.heard = list(heard)
        self.spoken = []

    async def transcribe(self, pcm):
        return Heard(self.heard.pop(0), "en")

    async def speak(self, text, language="en", voice=None):
        self.spoken.append(text)
        return tone(40)


def test_voice_stream_full_call():
    s, st = make(voice_stream_token="vt")
    st.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES ('CA1', 1, ?, 'queued', 'x')", (MOBILE,))
    speech = FakeSpeech(["Yes go ahead", "Stop calling me"])
    app = create_app(s, st, OfflineLLM(lambda *a: TURN), RecordingGateway(), speech, run_sender=False)
    client = TestClient(app)
    audio = base64.b64encode(tone(600) + silence(900)).decode()
    with client.websocket_connect("/exotel/stream?token=vt") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({"event": "start", "stream_sid": "S1", "start": {"stream_sid": "S1", "call_sid": "CA1"}}))
        first = json.loads(ws.receive_text())
        assert first["event"] == "media" and first["stream_sid"] == "S1"
        assert json.loads(ws.receive_text())["event"] == "mark"
        ws.send_text(json.dumps({"event": "media", "media": {"payload": audio}}))
        ws.send_text(json.dumps({"event": "media", "media": {"payload": audio}}))
        events = []
        try:
            while True:
                events.append(json.loads(ws.receive_text())["event"])
        except Exception:
            pass
    spoken = " ".join(speech.spoken)
    assert "AI assistant" in spoken
    assert spoken.index("AI assistant") < spoken.index("How do your supervisors") < spoken.index("removed your number")
    assert st.is_suppressed(MOBILE)
    assert st.one("SELECT 1 FROM touches WHERE direction = 'transcript'")


def test_voice_stream_rejects_unknown_calls_and_bad_token():
    s, st = make(voice_stream_token="vt")
    client = TestClient(create_app(s, st, OfflineLLM(lambda *a: TURN), RecordingGateway(), FakeSpeech([]), run_sender=False))
    with client.websocket_connect("/exotel/stream?token=vt") as ws:
        ws.send_text(json.dumps({"event": "start", "start": {"stream_sid": "S", "call_sid": "nope"}}))
        try:
            ws.receive_text()
            assert False, "should have closed"
        except Exception:
            pass
    try:
        with client.websocket_connect("/exotel/stream?token=bad") as ws:
            ws.receive_text()
        assert False
    except Exception:
        pass


class LongSpeech(FakeSpeech):
    async def speak(self, text, language="en", voice=None):
        self.spoken.append(text)
        return tone(3000)  # 3 s of audio per sentence: still playing when the caller cuts in


def test_caller_can_interrupt_the_agent():
    s, st = make(voice_stream_token="vt")
    st.execute("INSERT INTO calls (call_sid, prospect_id, phone, status, created_at) VALUES ('CA2', 1, ?, 'queued', 'x')", (MOBILE,))
    client = TestClient(create_app(s, st, OfflineLLM(lambda *a: TURN), RecordingGateway(), LongSpeech(["haan bolo"]), run_sender=False))
    with client.websocket_connect("/exotel/stream?token=vt") as ws:
        ws.send_text(json.dumps({"event": "start", "start": {"stream_sid": "S2", "call_sid": "CA2"}}))
        ws.send_text(json.dumps({"event": "media", "media": {"payload": base64.b64encode(tone(400)).decode()}}))
        seen = []
        for _ in range(400):
            ev = json.loads(ws.receive_text())["event"]
            seen.append(ev)
            if ev == "clear":
                break
    assert "clear" in seen


def test_sentences_split_for_faster_first_audio():
    from fieldos_sales.server import split_sentences
    assert split_sentences("Achha. Kitni sites chal rahi hain? Bataiye!") == ["Achha.", "Kitni sites chal rahi hain?", "Bataiye!"]
    assert split_sentences("जी। कितनी sites हैं?") == ["जी।", "कितनी sites हैं?"]
