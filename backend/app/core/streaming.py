from __future__ import annotations
import asyncio
import json
import time
import logging
from typing import Dict, Set, Optional, Callable, Any
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger("sangam.streaming")


class StreamManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._actor_map: Dict[str, str] = {}
        self._ws_actor: Dict[int, str] = {}
        self._tasks: Dict[int, asyncio.Task] = {}

    async def connect(self, ws: WebSocket, actor_id: str) -> None:
        await ws.accept()
        ws_key = id(ws)
        self._ws_actor[ws_key] = actor_id
        if actor_id not in self._connections:
            self._connections[actor_id] = set()
        self._connections[actor_id].add(ws)
        self._tasks[ws_key] = asyncio.create_task(self._keepalive(ws, actor_id))
        await self._send(ws, "connected", {"actor_id": actor_id})
        logger.info("WS connected: actor=%s", actor_id[:8])

    async def disconnect(self, ws: WebSocket) -> None:
        ws_key = id(ws)
        actor_id = self._ws_actor.pop(ws_key, "")
        if actor_id and actor_id in self._connections:
            self._connections[actor_id].discard(ws)
            if not self._connections[actor_id]:
                del self._connections[actor_id]
        task = self._tasks.pop(ws_key, None)
        if task:
            task.cancel()
        logger.info("WS disconnected: actor=%s", actor_id[:8] if actor_id else "unknown")

    async def send_to_actor(self, actor_id: str, event: str, data: dict) -> int:
        sent = 0
        for ws in self._connections.get(actor_id, set()).copy():
            try:
                await self._send(ws, event, data)
                sent += 1
            except Exception:
                await self.disconnect(ws)
        return sent

    async def send_to_workflow_participants(
        self, actor_ids: list[str], event: str, data: dict
    ) -> int:
        total = 0
        for aid in actor_ids:
            total += await self.send_to_actor(aid, event, data)
        return total

    async def broadcast(self, event: str, data: dict) -> int:
        total = 0
        for actor_id in list(self._connections.keys()):
            total += await self.send_to_actor(actor_id, event, data)
        return total

    async def _send(self, ws: WebSocket, event: str, data: dict) -> None:
        payload = json.dumps({"event": event, "data": data, "ts": time.time()})
        await ws.send_text(payload)

    async def _keepalive(self, ws: WebSocket, actor_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(25)
                try:
                    await self._send(ws, "ping", {})
                except Exception:
                    await self.disconnect(ws)
                    break
        except asyncio.CancelledError:
            pass

    async def handle_message(self, ws: WebSocket, raw: str) -> None:
        try:
            msg = json.loads(raw)
            event = msg.get("event", "")
            data = msg.get("data", {})
            actor_id = self._ws_actor.get(id(ws), "")

            if event == "pong":
                pass
            elif event == "subscribe_workflow":
                wf_id = data.get("workflow_id")
                if wf_id and actor_id:
                    key = f"wf:{wf_id}"
                    if key not in self._connections:
                        self._connections[key] = set()
                    self._connections[key].add(ws)
                    await self._send(ws, "subscribed", {"workflow_id": wf_id})
            elif event == "voice_chunk":
                await self._handle_voice_chunk(ws, actor_id, data)
            else:
                await self._send(ws, "error", {"message": f"Unknown event: {event}"})
        except json.JSONDecodeError:
            if actor_id:
                await self._send(ws, "error", {"message": "Invalid JSON"})

    async def _handle_voice_chunk(self, ws: WebSocket, actor_id: str, data: dict) -> None:
        chunk = data.get("audio", "")
        lang = data.get("language", "unknown")
        final = data.get("final", False)
        try:
            from app.core.sarvam import SarvamAI
            sarvam = SarvamAI()
            import base64
            audio_bytes = base64.b64decode(chunk) if isinstance(chunk, str) else b""
            if audio_bytes:
                result = await sarvam.speech_to_text(
                    audio_data=audio_bytes,
                    filename="stream.wav",
                    language_code=lang,
                )
                await self._send(ws, "voice_transcript", {
                    "text": result.transcript,
                    "language": result.language_code,
                    "final": final,
                })
        except Exception as e:
            logger.error("Voice chunk error: %s", e)


stream_manager = StreamManager()


async def notify_workflow_event(
    workflow_id: str,
    actor_ids: list[str],
    event: str,
    data: dict,
) -> int:
    return await stream_manager.send_to_workflow_participants(
        actor_ids, event, {"workflow_id": workflow_id, **data}
    )


async def notify_approval_event(
    approval_id: str,
    workflow_id: str,
    status: str,
    actor_ids: list[str],
) -> int:
    return await stream_manager.send_to_workflow_participants(
        actor_ids,
        "approval_update",
        {"approval_id": approval_id, "status": status, "workflow_id": workflow_id},
    )
