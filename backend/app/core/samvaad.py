"""Sarvam Voice Agents (Samvaad) client.

Samvaad is the hosted voice-agent platform: agents are built in its dashboard,
and this backend drives them over its REST API and real-time WebSocket.

API contract (https://docs.sarvam.ai/voice-agents/api/introduction):
  * Auth is an ``X-API-Key`` header carrying the Voice Agents key. It is NOT the
    regular Sarvam ``api-subscription-key`` and the two are not interchangeable.
  * Every service has its own base URL under https://apps.sarvam.ai/api:
      app-authoring  deployments   /v1/orgs/{org}/workspaces/{ws}/deployments
      outbounds      instant calls /v1/orgs/{org}/workspaces/{ws}/outbounds
      analytics      interactions  /v1/{org}/{ws}/{app_id}/interactions
                     transcripts   /v1/{org}/{ws}/{app_id}/transcripts/{interaction_id}
  * An outbound call is fire-and-forget: the response is only an attempt_id, and
    the outcome (status, duration, transcript) arrives later on the webhook URL
    passed in webhook_config. The payload carries no signature, so the URL itself
    holds a per-call secret (see app/api/voice_agents.py).
  * interaction_id looks like ``20261007/<uuid>``; the slash is part of the id.

Real-time voice uses ``sarvam-conv-ai-sdk`` (AsyncSamvaadAgent): it fetches a
signed WebSocket URL with the key and streams 16-bit PCM mono. It runs here, on
the server, and the phone talks to our proxy; the key never leaves the backend.

Fixture mode (no key, or USE_FIXTURES=true) returns canned responses through
the same code paths, and FixtureSamvaadAgent stands in for the SDK agent.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.config import settings
from app.core import fixtures

logger = logging.getLogger("sangam.samvaad")

LANGUAGE_NAMES = {
    "Bengali", "Gujarati", "Kannada", "Malayalam", "Tamil", "Telugu", "Punjabi",
    "Sanskrit", "Odia", "Marathi", "Hindi", "English", "Assamese",
}
SESSION_SAMPLE_RATE = 16000
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class SamvaadNotConfigured(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            detail="Voice agents are not configured: set SAMVAAD_ORG_ID and SAMVAAD_WORKSPACE_ID",
        )


def _upstream_error(resp: httpx.Response) -> HTTPException:
    """Map a Samvaad error to one we can show. Never echo the key or raw headers."""
    try:
        body = resp.json()
        detail = body.get("detail") or body.get("error") or body
    except ValueError:
        detail = resp.text[:300]
    logger.warning("Samvaad %s %s -> %s", resp.request.method, resp.request.url.path, resp.status_code)
    if resp.status_code in (401, 403):
        # Our key is wrong or lacks access. That is a server problem, not the caller's.
        return HTTPException(status_code=502, detail="Voice agent platform rejected the server's API key")
    if resp.status_code == 429:
        return HTTPException(status_code=429, detail="Voice agent platform is rate limiting; retry shortly")
    if resp.status_code in (400, 404, 409, 422):
        return HTTPException(status_code=resp.status_code, detail=detail)
    return HTTPException(status_code=502, detail="Voice agent platform error")


class SamvaadClient:
    def __init__(
        self,
        api_key: str | None = None,
        org_id: str | None = None,
        workspace_id: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = (api_key if api_key is not None else settings.sarvam_samvaad_api_key or "").strip()
        self.org_id = (org_id if org_id is not None else settings.samvaad_org_id or "").strip()
        self.workspace_id = (workspace_id if workspace_id is not None else settings.samvaad_workspace_id or "").strip()
        self.base = settings.samvaad_api_base.rstrip("/")
        self.use_fixtures = settings.use_fixtures or not self.api_key
        self._transport = transport

    # ------------------------------------------------------------------ plumbing
    def _require_scope(self) -> None:
        if not self.use_fixtures and not (self.org_id and self.workspace_id):
            raise SamvaadNotConfigured()

    @property
    def _org(self) -> str:
        return quote(self.org_id or "fixture-org", safe="")

    @property
    def _ws(self) -> str:
        return quote(self.workspace_id or "fixture-workspace", safe="")

    def _scoped(self, service: str, resource: str) -> str:
        return f"{self.base}/{service}/v1/orgs/{self._org}/workspaces/{self._ws}/{resource}"

    def _analytics(self, app_id: str, resource: str) -> str:
        return f"{self.base}/analytics/v1/{self._org}/{self._ws}/{quote(app_id, safe='')}/{resource}"

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
            try:
                resp = await client.request(method, url, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                logger.warning("Samvaad %s unreachable: %s", method, type(exc).__name__)
                raise HTTPException(status_code=502, detail="Voice agent platform unreachable") from exc
        if resp.status_code >= 400:
            raise _upstream_error(resp)
        return resp.json() if resp.content else {}

    # ---------------------------------------------------------------- deployments
    async def list_deployments(self, offset: int = 0, limit: int = 50) -> Any:
        self._require_scope()
        if self.use_fixtures:
            return fixtures.samvaad_deployments()
        return await self._request(
            "GET", self._scoped("app-authoring", "deployments"), params={"offset": offset, "limit": limit}
        )

    async def get_deployment(self, deployment_id: str) -> Any:
        self._require_scope()
        if self.use_fixtures:
            return fixtures.samvaad_deployment(deployment_id)
        return await self._request(
            "GET", self._scoped("app-authoring", f"deployments/{quote(deployment_id, safe='')}")
        )

    async def create_deployment(self, body: dict[str, Any]) -> Any:
        self._require_scope()
        if self.use_fixtures:
            return fixtures.samvaad_deployment("dep-fixture", body)
        return await self._request("POST", self._scoped("app-authoring", "deployments"), json=body)

    async def update_deployment_status(self, deployment_id: str, action: str) -> Any:
        """action is "pause" (stop taking inbound calls) or "resume"."""
        self._require_scope()
        if self.use_fixtures:
            status = "paused" if action == "pause" else "active"
            return {**fixtures.samvaad_deployment(deployment_id), "status": status}
        return await self._request(
            "PUT",
            self._scoped("app-authoring", f"deployments/{quote(deployment_id, safe='')}/status"),
            json={"action": action},
        )

    # ------------------------------------------------------------------- outbound
    async def create_outbound_call(
        self,
        *,
        app_id: str,
        app_version: int,
        connection_id: str,
        agent_phone_number: str,
        user_phone_number: str,
        webhook_url: str | None,
        webhook_metadata: dict[str, Any] | None = None,
        agent_variables: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> str:
        """Place one call now. Returns Samvaad's attempt_id; the outcome comes on the webhook."""
        self._require_scope()
        app_config: dict[str, Any] = {
            "app_id": app_id,
            "app_version": app_version,
            "connection_config": {"connection_id": connection_id, "agent_phone_number": agent_phone_number},
        }
        if agent_variables:
            app_config["agent_variables"] = agent_variables
        if overrides:
            app_config["app_overrides"] = overrides
        body: dict[str, Any] = {"app_config": app_config, "user_config": {"user_phone_number": user_phone_number}}
        if webhook_url:
            body["webhook_config"] = {"url": webhook_url, "metadata": webhook_metadata or None}
        if self.use_fixtures:
            return fixtures.samvaad_outbound_attempt_id()
        data = await self._request("POST", self._scoped("outbounds", "outbounds"), json=body)
        attempt_id = (data or {}).get("attempt_id")
        if not attempt_id:
            raise HTTPException(status_code=502, detail="Voice agent platform returned no attempt_id")
        return str(attempt_id)

    # ------------------------------------------------------------------ analytics
    async def list_interactions(
        self,
        app_id: str,
        *,
        start_datetime: str,
        end_datetime: str,
        limit: int = 20,
        offset: int = 0,
        include_transcript: bool = False,
    ) -> Any:
        self._require_scope()
        if self.use_fixtures:
            return fixtures.samvaad_interactions(app_id, include_transcript)
        params = {
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "limit": limit,
            "offset": offset,
            "include_transcript": str(include_transcript).lower(),
            "sort_by": "start_datetime",
            "sort_order": "desc",
        }
        return await self._request("GET", self._analytics(app_id, "interactions"), params=params)

    async def get_transcript(self, app_id: str, interaction_id: str) -> dict[str, Any]:
        self._require_scope()
        if self.use_fixtures:
            return fixtures.samvaad_transcript(interaction_id)
        # The <YYYYMMDD>/<id> slash is sent as is; quote everything else.
        safe_id = quote(interaction_id, safe="/")
        return await self._request("GET", self._analytics(app_id, f"transcripts/{safe_id}"))


# ---------------------------------------------------------------------------
# Real-time sessions
# ---------------------------------------------------------------------------

TranscriptCb = Callable[[str, str], Awaitable[None]]  # (role "user"|"agent", text)
AudioCb = Callable[[bytes, int], Awaitable[None]]  # (pcm_s16le, sample_rate)
EventCb = Callable[[str, dict[str, Any]], Awaitable[None]]  # (event type, extra)


class VoiceSession(Protocol):
    async def start(self) -> None: ...
    async def wait_for_connect(self, timeout: float | None = 5.0) -> bool: ...
    async def wait_for_disconnect(self) -> None: ...
    async def send_audio(self, pcm: bytes) -> None: ...
    async def send_text(self, text: str) -> None: ...
    async def stop(self) -> None: ...
    def get_interaction_id(self) -> str | None: ...


class _SdkSession:
    """Adapter over sarvam_conv_ai_sdk.AsyncSamvaadAgent in headless mode."""

    def __init__(self, agent: Any):
        self._agent = agent

    async def start(self) -> None:
        await self._agent.start()

    async def wait_for_connect(self, timeout: float | None = 5.0) -> bool:
        return bool(await self._agent.wait_for_connect(timeout=timeout))

    async def wait_for_disconnect(self) -> None:
        await self._agent.wait_for_disconnect()

    async def send_audio(self, pcm: bytes) -> None:
        await self._agent.send_audio(pcm)

    async def send_text(self, text: str) -> None:
        await self._agent.send_text(text)

    async def stop(self) -> None:
        await self._agent.stop()

    def get_interaction_id(self) -> str | None:
        return self._agent.get_interaction_id()


class FixtureSamvaadAgent:
    """Canned stand-in for a live session: greets, then answers each turn.

    Speaks 0.1 s of silence per turn so the client exercises its real playback
    path, and reports the user's audio as a transcript once enough has arrived.
    """

    GREETING = "Namaste! This is a test voice agent. How can I help you today?"

    def __init__(self, on_transcript: TranscriptCb, on_audio: AudioCb, on_event: EventCb):
        self._on_transcript = on_transcript
        self._on_audio = on_audio
        self._on_event = on_event
        self._connected = asyncio.Event()
        self._done = asyncio.Event()
        self._interaction_id = f"fixture/{uuid.uuid4()}"
        self._audio_bytes = 0

    async def _reply(self, text: str) -> None:
        await self._on_transcript("agent", text)
        await self._on_audio(b"\x00\x00" * (SESSION_SAMPLE_RATE // 10), SESSION_SAMPLE_RATE)

    async def start(self) -> None:
        self._connected.set()
        await self._on_event("interaction_connected", {"interaction_id": self._interaction_id})
        await self._reply(self.GREETING)

    async def wait_for_connect(self, timeout: float | None = 5.0) -> bool:
        return self._connected.is_set()

    async def wait_for_disconnect(self) -> None:
        await self._done.wait()

    async def send_audio(self, pcm: bytes) -> None:
        self._audio_bytes += len(pcm)
        # One second of 16 kHz s16le audio counts as one user turn.
        if self._audio_bytes >= SESSION_SAMPLE_RATE * 2:
            self._audio_bytes = 0
            await self._on_transcript("user", "(fixture) I would like to book an appointment.")
            await self._reply("Sure. Which day works for you?")

    async def send_text(self, text: str) -> None:
        await self._on_transcript("user", text)
        await self._reply(f"You said: {text}")

    async def stop(self) -> None:
        if not self._done.is_set():
            self._done.set()

    def get_interaction_id(self) -> str | None:
        return self._interaction_id


def open_voice_session(
    *,
    app_id: str,
    app_version: int | None,
    user_identifier: str,
    on_transcript: TranscriptCb,
    on_audio: AudioCb,
    on_event: EventCb,
    agent_variables: dict[str, Any] | None = None,
    initial_language_name: str | None = None,
) -> VoiceSession:
    """Build a server-side session for one caller. Nothing connects until start()."""
    client = SamvaadClient()
    client._require_scope()
    if client.use_fixtures:
        return FixtureSamvaadAgent(on_transcript, on_audio, on_event)

    from pydantic import SecretStr
    from sarvam_conv_ai_sdk import (
        AsyncSamvaadAgent,
        InteractionConfig,
        InteractionType,
        Role,
        ServerAudioChunkMsg,
        ServerEventBase,
        ServerTranscriptMsg,
    )
    from sarvam_conv_ai_sdk.messages.types import UserIdentifierType

    async def transcript_cb(msg: ServerTranscriptMsg) -> None:
        await on_transcript("user" if msg.role == Role.USER else "agent", msg.content)

    async def audio_cb(msg: ServerAudioChunkMsg) -> None:
        if msg.audio_base64:
            await on_audio(base64.b64decode(msg.audio_base64), int(msg.sample_rate or SESSION_SAMPLE_RATE))

    async def event_cb(event: ServerEventBase) -> None:
        kind = str(getattr(event, "type", "event"))
        kind = getattr(getattr(event, "type", None), "value", kind)
        extra: dict[str, Any] = {}
        interaction_id = getattr(event, "interaction_id", None)
        if interaction_id:
            extra["interaction_id"] = interaction_id
        await on_event(kind, extra)

    config_kwargs: dict[str, Any] = dict(
        user_identifier_type=UserIdentifierType.CUSTOM,
        user_identifier=user_identifier,
        org_id=client.org_id,
        workspace_id=client.workspace_id,
        app_id=app_id,
        interaction_type=InteractionType.CALL,
        sample_rate=SESSION_SAMPLE_RATE,
    )
    if app_version is not None:
        config_kwargs["version"] = app_version
    if agent_variables:
        config_kwargs["agent_variables"] = agent_variables
    if initial_language_name:
        config_kwargs["initial_language_name"] = initial_language_name

    agent = AsyncSamvaadAgent(
        api_key=SecretStr(client.api_key),
        config=InteractionConfig(**config_kwargs),
        transcript_callback=transcript_cb,
        audio_callback=audio_cb,
        event_callback=event_cb,
        base_url=f"{client.base}/app-runtime/",
    )
    return _SdkSession(agent)


def transcript_from_webhook(turns: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Normalise the webhook's interaction_transcript to [{role, content}]."""
    out: list[dict[str, str]] = []
    for turn in turns or []:
        role = "agent" if str(turn.get("role")) in ("agent", "assistant", "bot") else "user"
        out.append({"role": role, "content": str(turn.get("en_text") or turn.get("content") or "")})
    return out


def transcript_from_analytics(data: dict[str, Any]) -> list[dict[str, str]]:
    """Normalise GET transcripts (roles assistant/user) to [{role, content, language}]."""
    out: list[dict[str, str]] = []
    for msg in (data or {}).get("messages") or []:
        out.append({
            "role": "agent" if msg.get("role") == "assistant" else "user",
            "content": str(msg.get("content") or ""),
            "language": str(msg.get("language_name") or ""),
        })
    return out
