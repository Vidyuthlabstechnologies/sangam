"""Speech (Sarvam) and outbound dialling (Exotel).

Sarvam request shapes follow the sangam backend's app/core/sarvam.py, which
is already used with the live API. The Exotel parts follow Exotel's public
"connect a number to a call flow" API and the Voicebot applet's WebSocket
stream; test them on your own number first (see README).
"""
from __future__ import annotations

import base64
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from .audio import RATE, pcm_to_wav, wav_to_pcm
from .config import Settings

log = logging.getLogger("fieldos_sales.telephony")

SARVAM_BASE = "https://api.sarvam.ai"
LANG_TO_SARVAM = {"en": "en-IN", "hi": "hi-IN", "te": "te-IN"}
SARVAM_TO_LANG = {v: k for k, v in LANG_TO_SARVAM.items()}


@dataclass
class Heard:
    text: str
    language: str | None  # en / hi / te when Sarvam recognises one of them


class Speech:
    """Sarvam speech-to-text and text-to-speech, tuned for phone calls.

    One HTTP connection is kept open and reused (no new TLS handshake per
    turn), and spoken audio is cached, so fixed lines such as the greeting,
    "haan ji" acknowledgements and the goodbye play with no delay.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.headers = {"api-subscription-key": settings.sarvam_api_key}
        self.client = client or httpx.AsyncClient(timeout=20, limits=httpx.Limits(max_keepalive_connections=4))
        self.cache: dict[tuple[str, str], bytes] = {}

    async def transcribe(self, pcm: bytes) -> Heard:
        files = {
            "file": ("utterance.wav", pcm_to_wav(pcm), "audio/wav"),
            "model": (None, "saaras:v3"),
            "mode": (None, "transcribe"),
            "language_code": (None, "unknown"),
        }
        r = await self.client.post(f"{SARVAM_BASE}/speech-to-text", headers=self.headers, files=files)
        r.raise_for_status()
        data = r.json()
        return Heard(text=data.get("transcript", ""), language=SARVAM_TO_LANG.get(data.get("language_code", "")))

    def _voice(self, voice: str | None, language: str = "en") -> tuple[str, str]:
        """(model, speaker). A "{lang}" in the speaker picks the per-language style of the same
        voice, e.g. simran_{lang}_sales -> simran_en_sales / simran_hi_sales (Telugu uses hi)."""
        model, _, speaker = (voice or "").partition("/")
        speaker = (speaker or self.settings.sarvam_speaker).replace("{lang}", language if language in ("en", "hi") else "hi")
        return (model or self.settings.sarvam_tts_model), speaker

    async def speak(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        model, speaker = self._voice(voice, language)
        key = (language, text, model, speaker)
        if key in self.cache:
            return self.cache[key]
        payload = {
            "text": text,
            "target_language_code": LANG_TO_SARVAM.get(language, "en-IN"),
            "speaker": speaker,
            "model": model,
            "pace": self.settings.voice_pace,
            "speech_sample_rate": RATE,
        }
        r = await self.client.post(f"{SARVAM_BASE}/text-to-speech",
                                   headers={**self.headers, "Content-Type": "application/json"}, json=payload)
        r.raise_for_status()
        audios = r.json().get("audios", [])
        pcm = wav_to_pcm(base64.b64decode(audios[0]), RATE) if audios else b""
        if len(text) <= 300 and len(self.cache) < 500:
            self.cache[key] = pcm
        return pcm

    async def speak_stream(self, text: str, language: str = "en", voice: str | None = None) -> AsyncIterator[bytes]:
        """Yield 8 kHz 16-bit PCM as Sarvam produces it (HTTP streaming, linear16).

        Experimental (SARVAM_TTS_STREAM=1): not yet checked against the live API. Cached lines and
        any streaming error fall back to the normal request, so a call never goes silent because of it.
        """
        model, speaker = self._voice(voice, language)
        key = (language, text, model, speaker)
        if key in self.cache or not self.settings.tts_stream:
            yield await self.speak(text, language, voice)
            return
        payload = {"text": text, "language_code": LANG_TO_SARVAM.get(language, "en-IN"), "speaker": speaker,
                   "model": model, "pace": self.settings.voice_pace, "output_audio_codec": "linear16",
                   "speech_sample_rate": RATE}
        got, carry = bytearray(), b""
        try:
            async with self.client.stream("POST", f"{SARVAM_BASE}/text-to-speech/stream", json=payload,
                                          headers={**self.headers, "Content-Type": "application/json"}) as r:
                r.raise_for_status()
                if "json" in r.headers.get("content-type", ""):
                    raise httpx.HTTPError("stream returned JSON, not audio")
                async for part in r.aiter_bytes():
                    data = carry + part
                    if not got and data[:4] == b"RIFF":  # a WAV header slipped in: drop it
                        if len(data) < 44:
                            carry = data
                            continue
                        data = data[44:]
                    cut = len(data) - len(data) % 2
                    carry = data[cut:]
                    if cut:
                        got += data[:cut]
                        yield data[:cut]
        except httpx.HTTPError as e:
            if got:
                log.warning("TTS stream broke mid-sentence: %s", e)
                return
            log.warning("TTS stream failed, using the normal request: %s", e)
            yield await self.speak(text, language, voice)
            return
        if len(text) <= 300 and len(self.cache) < 500:
            self.cache[key] = bytes(got)

    async def warm_up(self, lines: list[tuple[str, str]], voice: str | None = None) -> None:
        """Pre-render fixed lines (language, text) so they play instantly."""
        for language, text in lines:
            try:
                await self.speak(text, language, voice)
            except httpx.HTTPError:
                log.warning("could not pre-render %r", text[:40])


class ExotelDialer:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.s = settings
        self.client = client

    def configured(self) -> list[str]:
        missing = [name for name, v in (
            ("EXOTEL_SID", self.s.exotel_sid), ("EXOTEL_API_KEY", self.s.exotel_api_key),
            ("EXOTEL_API_TOKEN", self.s.exotel_api_token), ("EXOTEL_CALLER_ID", self.s.exotel_caller_id),
            ("EXOTEL_FLOW_URL", self.s.exotel_flow_url),
        ) if not v]
        return missing

    def dial(self, phone: str, prospect_id: int) -> str:
        """Ask Exotel to call `phone` and connect it to the Voicebot flow. Returns the call SID."""
        missing = self.configured()
        if missing:
            raise RuntimeError("Exotel not configured: " + ", ".join(missing))
        url = f"https://{self.s.exotel_subdomain}/v1/Accounts/{self.s.exotel_sid}/Calls/connect.json"
        data = {
            "From": phone,
            "CallerId": self.s.exotel_caller_id,
            "Url": self.s.exotel_flow_url,
            "CustomField": f"prospect:{prospect_id}",
            "TimeLimit": "600",
            "TimeOut": "30",
        }
        if self.s.public_base_url:
            data["StatusCallback"] = f"{self.s.public_base_url}/exotel/status?token={self.s.voice_stream_token}"
        client = self.client or httpx.Client(timeout=20)
        try:
            r = client.post(url, data=data, auth=(self.s.exotel_api_key, self.s.exotel_api_token))
            r.raise_for_status()
            return r.json()["Call"]["Sid"]
        finally:
            if self.client is None:
                client.close()
