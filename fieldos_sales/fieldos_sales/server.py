"""The always-on part: WhatsApp webhooks + sender, and the phone-call voice stream.

Run:  python -m fieldos_sales serve      (listens on 0.0.0.0:8090)

  POST /wa/waha?token=...       WAHA webhook (event "message")
  POST /wa/twilio               Twilio WhatsApp webhook (signature checked)
  WS   /exotel/stream?token=... Exotel Voicebot applet audio stream
  POST /exotel/status?token=... Exotel call status callback
  GET  /dashboard?token=...     call and chat insights (DASHBOARD_TOKEN)
  GET  /api/insights?token=...  the same as JSON
  GET  /health
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import random
import re
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse, JSONResponse

from .audio import UtteranceDetector, chunks
from .config import Settings
from .conversation import Conversation
from .dashboard import render as render_dashboard
from .insights import compute
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

    # ---- insights dashboard ------------------------------------------------
    def _dashboard_auth(token: str) -> None:
        if not settings.dashboard_token:
            raise HTTPException(status_code=403, detail="Set DASHBOARD_TOKEN in .env to open the dashboard.")
        if not _token_ok(settings.dashboard_token, token):
            raise HTTPException(status_code=403)

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(token: str = "") -> HTMLResponse:
        _dashboard_auth(token)
        data = await asyncio.to_thread(compute, store)
        return HTMLResponse(render_dashboard(data, live_url=f"api/insights?token={quote(token)}"),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                     "X-Frame-Options": "DENY"})

    @app.get("/api/insights")
    async def insights_json(token: str = "") -> JSONResponse:
        _dashboard_auth(token)
        return JSONResponse(await asyncio.to_thread(compute, store), headers={"Cache-Control": "no-store"})

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
                      outcome=f"status:{form.get('Status', 'unknown')}",
                      meta={"call_sid": sid, "duration": form.get("ConversationDuration")})
        return {"ok": True}

    @app.websocket("/exotel/stream")
    async def exotel_stream(ws: WebSocket) -> None:
        if not _token_ok(settings.voice_stream_token, ws.query_params.get("token")):
            await ws.close(code=1008)
            return
        await ws.accept()
        await VoiceSession(ws, store, llm, speech, settings).run()

    return app


STILL_THERE = {"en": "Hello, can you hear me?", "hi": "Hello, आवाज़ आ रही है?", "te": "Hello, వినిపిస్తోందా?"}
SILENCE_PROMPT_S = 7.0
BARGE_IN_MS = 240          # caller speech this long while we talk = they are interrupting
BACKCHANNEL_MIN_S = 0.8    # don't "haan ji" a one-word answer


def pick_voice(store: Store, settings: Settings) -> str:
    """A/B test: give each new call the voice with the fewest finished calls so far."""
    voices = settings.voices()
    if len(voices) == 1:
        return voices[0]
    counts = dict.fromkeys(voices, 0)
    for row in store.all("SELECT json_extract(meta, '$.voice') AS v, COUNT(*) AS n FROM touches "
                         "WHERE channel = 'call' AND direction = 'transcript' GROUP BY v"):
        if row["v"] in counts:
            counts[row["v"]] = row["n"]
    return min(voices, key=lambda v: (counts[v], voices.index(v)))


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?।])\s+", text.strip()) if p.strip()]
    return parts or [text]


class VoiceSession:
    """One phone call: caller audio in -> text -> conversation -> speech out.

    Built to feel like talking to a person:
      - the caller can interrupt; our audio stops at once
      - a short "haan ji" plays the moment they finish, while the reply is prepared
      - replies are spoken sentence by sentence, the first one as soon as it is ready
      - fixed lines are pre-rendered and cached
      - after a long silence it asks "can you hear me?" once
    """

    def __init__(self, ws: WebSocket, store: Store, llm: LLM, speech: Any, settings: Settings | None = None):
        self.ws, self.store, self.llm, self.speech = ws, store, llm, speech
        self.settings = settings or Settings()
        self.stream_sid: str | None = None
        self.convo: Conversation | None = None
        self.detector = UtteranceDetector(silence_ms=self.settings.end_of_turn_ms)
        self.call_row: Any = None
        self.play_until = 0.0          # monotonic time our queued audio finishes
        self.generation = 0            # bumped on barge-in so stale audio is dropped
        self.task: asyncio.Task | None = None
        self.queued: list[bytes] = []
        self.last_activity = time.monotonic()
        self.prompted_silence = False
        self.done = asyncio.Event()
        # Call metrics for the insights dashboard.
        self.started_at = time.monotonic()
        self.latencies_ms: list[int] = []
        self.barge_ins = 0
        self.silence_prompts = 0
        self.languages: list[str] = []
        self.ended_by = "caller"
        self.voice: str | None = None

    # ---- audio out ---------------------------------------------------------
    def playing(self) -> bool:
        return time.monotonic() < self.play_until

    async def send(self, payload: dict[str, Any]) -> None:
        await self.ws.send_text(json.dumps(payload))

    async def _send_audio(self, pcm: bytes, generation: int) -> None:
        if generation != self.generation or not pcm:
            return
        for chunk in chunks(pcm):
            await self.send({"event": "media", "stream_sid": self.stream_sid,
                             "media": {"payload": base64.b64encode(chunk).decode()}})
        await self.send({"event": "mark", "stream_sid": self.stream_sid, "mark": {"name": f"g{generation}"}})
        self.play_until = max(self.play_until, time.monotonic()) + len(pcm) / 16000

    async def say(self, text: str, language: str) -> float | None:
        """Speak text sentence by sentence; all sentences render in parallel, play in order.

        Returns when (monotonic) the first audio went out, for latency stats.
        """
        generation = self.generation
        first: float | None = None
        sentences = split_sentences(text)
        if self.settings.tts_stream and hasattr(self.speech, "speak_stream"):
            # Stream each sentence: the first words go out while the rest is still being made.
            for sentence in sentences:
                async for pcm in self.speech.speak_stream(sentence, language, voice=self.voice):
                    if generation != self.generation:
                        return first
                    await self._send_audio(pcm, generation)
                    if first is None and pcm:
                        first = time.monotonic()
            return first
        renders = [asyncio.create_task(self.speech.speak(sentence, language, voice=self.voice)) for sentence in sentences]
        for render in renders:
            pcm = await render
            await self._send_audio(pcm, generation)
            if first is None and pcm and generation == self.generation:
                first = time.monotonic()
        return first

    async def barge_in(self) -> None:
        self.barge_ins += 1
        self.generation += 1
        self.play_until = 0.0
        await self.send({"event": "clear", "stream_sid": self.stream_sid})

    # ---- call flow -----------------------------------------------------------
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
        self.voice = pick_voice(self.store, self.settings)
        self.convo = Conversation.load(self.store, self.llm, prospect, self.call_row["phone"], "call",
                                       agent_name=self.settings.agent_name, agent_gender=self.settings.agent_gender)
        await self.say(self.convo.opening(), self.convo.language)
        if hasattr(self.speech, "warm_up"):
            asyncio.create_task(self.speech.warm_up(self._fixed_lines(), voice=self.voice))
        return True

    def _fixed_lines(self) -> list[tuple[str, str]]:
        from .conversation import (
            AI_ANSWER,
            BACKCHANNELS,
            GOODBYE_OPT_OUT,
            HANDOVER,
            pick,
        )
        from .knowledge import PRICE_DEFLECTION
        lines = []
        for lang in ("en", "hi", "te"):
            lines += [(lang, b) for b in BACKCHANNELS[lang]]
            for table in (GOODBYE_OPT_OUT["call"], AI_ANSWER, HANDOVER, PRICE_DEFLECTION, STILL_THERE):
                for sentence in split_sentences(pick(table, lang, self.settings.agent_gender)):
                    lines.append((lang, sentence))
        return lines

    async def handle_utterance(self, pcm: bytes) -> None:
        assert self.convo is not None
        convo = self.convo
        if len(pcm) / 16000 >= BACKCHANNEL_MIN_S and random.random() < 0.8:
            asyncio.create_task(self.say(convo.backchannel(), convo.language))
        heard_at = time.monotonic()
        heard = await self.speech.transcribe(pcm)
        if not heard.text.strip():
            return
        if heard.language in ("en", "hi", "te"):
            convo.language = heard.language
            self.languages.append(heard.language)
        turn = await asyncio.to_thread(convo.respond, heard.text)
        first_audio = await self.say(turn.say, turn.language)
        if first_audio is not None:
            # What the caller feels: our end-of-turn wait plus STT, thinking and the first sentence's TTS.
            self.latencies_ms.append(int((first_audio - heard_at) * 1000) + self.settings.end_of_turn_ms)
        self.prompted_silence = False
        self.last_activity = time.monotonic()
        if turn.end:
            self.ended_by = "agent"
            await asyncio.sleep(max(0.0, self.play_until - time.monotonic()) + 0.6)
            self.done.set()

    async def _worker(self, pcm: bytes) -> None:
        try:
            await self.handle_utterance(pcm)
            while self.queued and not self.done.is_set():
                await self.handle_utterance(b"".join(self.queued.pop(0) for _ in range(len(self.queued))))
        except Exception:
            log.exception("turn failed")

    async def on_media(self, pcm: bytes) -> None:
        utterances = self.detector.feed(pcm)
        if self.detector.speaking:
            self.last_activity = time.monotonic()
            if self.playing() and self.detector._speech_ms >= BARGE_IN_MS:
                await self.barge_in()
        for utterance in utterances:
            if self.task and not self.task.done():
                self.queued.append(utterance)
            else:
                self.task = asyncio.create_task(self._worker(utterance))
        idle = time.monotonic() - max(self.last_activity, self.play_until)
        if (idle > SILENCE_PROMPT_S and not self.prompted_silence and not self.playing()
                and not (self.task and not self.task.done()) and self.convo):
            self.prompted_silence = True
            self.silence_prompts += 1
            self.last_activity = time.monotonic()
            asyncio.create_task(self.say(STILL_THERE[self.convo.language], self.convo.language))

    async def run(self) -> None:
        try:
            while not self.done.is_set():
                try:
                    raw = await asyncio.wait_for(self.ws.receive_text(), timeout=1.0)
                except TimeoutError:
                    continue
                event = json.loads(raw)
                kind = event.get("event")
                if kind == "start":
                    if not await self.start(event):
                        break
                elif kind == "media" and self.convo:
                    await self.on_media(base64.b64decode((event.get("media") or {}).get("payload", "")))
                elif kind == "stop":
                    break
        except WebSocketDisconnect:
            pass
        except Exception:
            self.ended_by = "error"
            log.exception("voice session failed")
        finally:
            if self.task and not self.task.done():
                self.task.cancel()
            touch_id = None
            if self.convo and self.call_row:
                touch_id = self.store.log("call", "transcript", prospect_id=self.call_row["prospect_id"],
                                          phone=self.call_row["phone"], text=self.convo.transcript(),
                                          outcome=self.convo.outcome or "ended", meta=self.metrics())
            try:
                await self.ws.close()
            except Exception:
                log.debug("socket already closed")
            if touch_id and self.settings.auto_summarise:
                from .insights import summarise_call
                try:
                    await asyncio.to_thread(summarise_call, self.store, self.llm, touch_id)
                except Exception:
                    log.exception("call summary failed (run `insights --summarise` later)")

    def metrics(self) -> dict[str, Any]:
        convo = self.convo
        lat = sorted(self.latencies_ms)
        prospect_turns = sum(1 for m in convo.history if m["role"] == "user") if convo else 0
        return {
            "call_sid": self.call_row["call_sid"] if self.call_row else None,
            "duration_s": round(time.monotonic() - self.started_at, 1),
            "prospect_turns": prospect_turns,
            "price_asks": convo.price_asks if convo else 0,
            "language": convo.language if convo else "en",
            "languages": sorted(set(self.languages)),
            "latency_ms_avg": int(sum(lat) / len(lat)) if lat else None,
            "latency_ms_p90": lat[min(len(lat) - 1, int(len(lat) * 0.9))] if lat else None,
            "barge_ins": self.barge_ins,
            "silence_prompts": self.silence_prompts,
            "ended_by": self.ended_by if not (convo and convo.outcome) else "agent",
            "voice": self.voice,
            "tts_stream": self.settings.tts_stream,
        }
