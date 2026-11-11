"""The always-on part: WhatsApp webhooks + sender, and the phone-call voice stream.

Run:  python -m fieldos_sales serve      (listens on 0.0.0.0:8090)

  POST /wa/waha?token=...       WAHA webhook (event "message")
  POST /wa/twilio               Twilio WhatsApp webhook (signature checked)
  WS   /exotel/stream?token=... Exotel Voicebot applet audio stream
  POST /exotel/status?token=... Exotel call status callback
  GET  /health
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)

from .audio import UtteranceDetector, chunks
from .config import Settings
from .conversation import Conversation
from .llm import LLM, make_llm
from .prospects import normalise_indian_phone
from .store import Store
from .telephony import Speech
from .whatsapp import (
    Gateway,
    handle_inbound,
    make_gateway,
    parse_waha_event,
    sender_loop,
    twilio_signature_ok,
)

log = logging.getLogger("fieldos_sales.server")


def _token_ok(expected: str, given: str | None) -> bool:
    return bool(expected) and hmac.compare_digest(expected, given or "")


def create_app(settings: Settings | None = None, store: Store | None = None, llm: LLM | None = None,
               gateway: Gateway | None = None, speech: Any = None, run_sender: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.db_path)
    llm = llm or make_llm(settings, store)
    gateway = gateway or make_gateway(settings)
    speech = speech or Speech(settings)
    stop = asyncio.Event()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(sender_loop(store, settings, gateway, stop)) if run_sender else None
        yield
        stop.set()
        if task:
            await task

    app = FastAPI(title="FieldOS sales agents", lifespan=lifespan)
    app.state.store, app.state.settings, app.state.gateway = store, settings, gateway

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "live": settings.live, "whatsapp_gateway": gateway.name}

    # ---- WhatsApp ----------------------------------------------------------
    @app.post("/wa/waha")
    async def waha_webhook(request: Request, background: BackgroundTasks, token: str = "") -> dict[str, bool]:
        if not _token_ok(settings.wa_webhook_token, token):
            raise HTTPException(status_code=403)
        try:
            event = await request.json()
        except ValueError:
            raise HTTPException(status_code=400)
        parsed = parse_waha_event(event) if isinstance(event, dict) else None
        if parsed:
            background.add_task(handle_inbound, store, llm, settings, gateway, *parsed)
        return {"ok": True}

    @app.post("/wa/twilio")
    async def twilio_webhook(request: Request, background: BackgroundTasks) -> dict[str, bool]:
        form = {k: str(v) for k, v in (await request.form()).items()}
        url = f"{settings.public_base_url}/wa/twilio"
        if not settings.twilio_auth_token or not twilio_signature_ok(
                settings.twilio_auth_token, url, form, request.headers.get("X-Twilio-Signature", "")):
            raise HTTPException(status_code=403)
        phone = normalise_indian_phone(form.get("From", "").replace("whatsapp:", ""))
        text = form.get("Body", "").strip()
        if phone and text:
            background.add_task(handle_inbound, store, llm, settings, gateway, phone, text)
        return {"ok": True}

    # ---- phone calls -------------------------------------------------------
    @app.post("/exotel/status")
    async def exotel_status(request: Request, token: str = "") -> dict[str, bool]:
        if not _token_ok(settings.voice_stream_token, token):
            raise HTTPException(status_code=403)
        form = {k: str(v) for k, v in (await request.form()).items()}
        sid = form.get("CallSid", "")
        row = store.one("SELECT * FROM calls WHERE call_sid = ?", (sid,))
        if row:
            store.execute("UPDATE calls SET status = ? WHERE call_sid = ?", (form.get("Status", "unknown"), sid))
            store.log("call", "event", prospect_id=row["prospect_id"], phone=row["phone"],
                      outcome=f"status:{form.get('Status', 'unknown')}", meta={"duration": form.get("ConversationDuration")})
        return {"ok": True}

    @app.websocket("/exotel/stream")
    async def exotel_stream(ws: WebSocket) -> None:
        if not _token_ok(settings.voice_stream_token, ws.query_params.get("token")):
            await ws.close(code=1008)
            return
        await ws.accept()
        await VoiceSession(ws, store, llm, speech).run()

    return app


class VoiceSession:
    """One phone call: caller audio in -> text -> conversation -> speech out."""

    def __init__(self, ws: WebSocket, store: Store, llm: LLM, speech: Any):
        self.ws, self.store, self.llm, self.speech = ws, store, llm, speech
        self.stream_sid: str | None = None
        self.convo: Conversation | None = None
        self.detector = UtteranceDetector()
        self.playing = False
        self.call_row: Any = None

    async def send(self, payload: dict[str, Any]) -> None:
        await self.ws.send_text(json.dumps(payload))

    async def say(self, text: str, language: str) -> float:
        pcm = await self.speech.speak(text, language)
        for chunk in chunks(pcm):
            await self.send({"event": "media", "stream_sid": self.stream_sid,
                             "media": {"payload": base64.b64encode(chunk).decode()}})
        await self.send({"event": "mark", "stream_sid": self.stream_sid, "mark": {"name": "turn"}})
        self.playing = True
        return len(pcm) / 16000  # seconds of audio

    async def start(self, event: dict[str, Any]) -> bool:
        start = event.get("start") or {}
        self.stream_sid = start.get("stream_sid") or event.get("stream_sid") or start.get("streamSid")
        call_sid = start.get("call_sid") or start.get("callSid") or ""
        self.call_row = self.store.one("SELECT * FROM calls WHERE call_sid = ?", (call_sid,))
        if not self.call_row:
            # Only calls this tool dialled get the agent.
            log.warning("stream for unknown call %r; closing", call_sid)
            return False
        prospect = self.store.prospect(self.call_row["prospect_id"])
        if not prospect or self.store.is_suppressed(self.call_row["phone"]):
            return False
        self.convo = Conversation.load(self.store, self.llm, prospect, self.call_row["phone"], "call")
        await self.say(self.convo.opening(), self.convo.language)
        return True

    async def on_utterance(self, pcm: bytes) -> bool:
        """Returns False when the call should end."""
        assert self.convo is not None
        if self.playing:  # caller talked over us: stop our audio
            await self.send({"event": "clear", "stream_sid": self.stream_sid})
            self.playing = False
        heard = await self.speech.transcribe(pcm)
        if not heard.text.strip():
            return True
        if heard.language in ("en", "hi", "te"):
            self.convo.language = heard.language
        turn = self.convo.respond(heard.text)
        seconds = await self.say(turn.say, turn.language)
        if turn.end:
            await asyncio.sleep(seconds + 0.5)
            return False
        return True

    async def run(self) -> None:
        try:
            while True:
                event = json.loads(await self.ws.receive_text())
                kind = event.get("event")
                if kind == "start":
                    if not await self.start(event):
                        break
                elif kind == "media" and self.convo:
                    payload = (event.get("media") or {}).get("payload", "")
                    for utterance in self.detector.feed(base64.b64decode(payload)):
                        if not await self.on_utterance(utterance):
                            raise StopAsyncIteration
                elif kind == "mark":
                    self.playing = False
                elif kind == "stop":
                    break
        except (WebSocketDisconnect, StopAsyncIteration):
            pass
        except Exception:
            log.exception("voice session failed")
        finally:
            if self.convo and self.call_row:
                self.store.log("call", "transcript", prospect_id=self.call_row["prospect_id"], phone=self.call_row["phone"],
                               text=self.convo.transcript(), outcome=self.convo.outcome or "ended")
            try:
                await self.ws.close()
            except Exception:
                pass
