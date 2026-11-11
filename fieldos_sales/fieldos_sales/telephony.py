"""Speech (Sarvam) and outbound dialling (Exotel).

Sarvam request shapes follow the sangam backend's app/core/sarvam.py, which
is already used with the live API. The Exotel parts follow Exotel's public
"connect a number to a call flow" API and the Voicebot applet's WebSocket
stream; test them on your own number first (see README).
"""
from __future__ import annotations

import base64
import logging
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
    def __init__(self, settings: Settings):
        self.settings = settings
        self.headers = {"api-subscription-key": settings.sarvam_api_key}

    async def transcribe(self, pcm: bytes) -> Heard:
        files = {
            "file": ("utterance.wav", pcm_to_wav(pcm), "audio/wav"),
            "model": (None, "saaras:v3"),
            "mode": (None, "transcribe"),
            "language_code": (None, "unknown"),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{SARVAM_BASE}/speech-to-text", headers=self.headers, files=files)
            r.raise_for_status()
            data = r.json()
        return Heard(text=data.get("transcript", ""), language=SARVAM_TO_LANG.get(data.get("language_code", "")))

    async def speak(self, text: str, language: str = "en") -> bytes:
        payload = {
            "text": text,
            "target_language_code": LANG_TO_SARVAM.get(language, "en-IN"),
            "speaker": self.settings.sarvam_speaker,
            "model": "bulbul:v3",
            "pace": 1.0,
            "speech_sample_rate": RATE,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{SARVAM_BASE}/text-to-speech",
                                  headers={**self.headers, "Content-Type": "application/json"}, json=payload)
            r.raise_for_status()
            audios = r.json().get("audios", [])
        if not audios:
            return b""
        return wav_to_pcm(base64.b64decode(audios[0]), RATE)


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
