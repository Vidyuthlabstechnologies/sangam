import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.actor import Actor
from app.core.security import decode_access_token
from app.core.streaming import stream_manager

logger = logging.getLogger("sangam.ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(""),
    session: AsyncSession = Depends(get_session),
):
    payload = decode_access_token(token)
    if not payload:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    actor_id = payload.get("sub", "")
    try:
        result = await session.execute(select(Actor).where(Actor.id == UUID(actor_id)))
        actor = result.scalar_one_or_none()
        if not actor or not actor.is_active:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    except Exception:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await stream_manager.connect(ws, actor_id)
    try:
        while True:
            raw = await ws.receive_text()
            await stream_manager.handle_message(ws, raw)
    except WebSocketDisconnect:
        stream_manager.disconnect(ws)
    except Exception as e:
        logger.error("WS error: %s", e)
        stream_manager.disconnect(ws)


@router.websocket("/ws/voice")
async def voice_stream_endpoint(
    ws: WebSocket,
    token: str = Query(""),
    language: str = Query("unknown"),
    session: AsyncSession = Depends(get_session),
):
    payload = decode_access_token(token)
    if not payload:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    actor_id = payload.get("sub", "")
    await stream_manager.connect(ws, actor_id)

    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            if msg.get("event") in ("voice_chunk", "audio_chunk"):
                import base64
                chunk = base64.b64decode(msg.get("data", ""))
                lang = msg.get("language", language)
                final = msg.get("final", False)
                if chunk:
                    from app.core.sarvam import SarvamAI
                    sarvam = SarvamAI()
                    result = await sarvam.speech_to_text(
                        audio_data=chunk,
                        filename="stream.wav",
                        language_code=lang,
                    )
                    await ws.send_text(json.dumps({
                        "event": "transcript",
                        "data": {"text": result.transcript, "final": final},
                    }))
            elif msg.get("event") == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        stream_manager.disconnect(ws)
    except Exception as e:
        logger.error("Voice WS error: %s", e)
        stream_manager.disconnect(ws)
