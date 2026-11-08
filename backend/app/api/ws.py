import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.core.oidc import InvalidAccessToken, link_actor, verify_access_token
from app.core.streaming import stream_manager
from app.core.access import actor_can_access_workflow_id

logger = logging.getLogger("sangam.ws")
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(""),
    session: AsyncSession = Depends(get_session),
):
    try:
        actor = await link_actor(session, verify_access_token(token))
    except InvalidAccessToken:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    actor_id = str(actor.id)

    async def can_subscribe(connected_actor_id: str, workflow_id: str) -> bool:
        try:
            return await actor_can_access_workflow_id(session, UUID(connected_actor_id), UUID(str(workflow_id)))
        except Exception:
            return False

    await stream_manager.connect(ws, actor_id)
    try:
        while True:
            raw = await ws.receive_text()
            await stream_manager.handle_message(ws, raw, can_subscribe=can_subscribe)
    except WebSocketDisconnect:
        await stream_manager.disconnect(ws)
    except Exception as e:
        logger.error("WS error: %s", e)
        await stream_manager.disconnect(ws)


@router.websocket("/ws/voice")
async def voice_stream_endpoint(
    ws: WebSocket,
    token: str = Query(""),
    language: str = Query("unknown"),
    session: AsyncSession = Depends(get_session),
):
    try:
        actor = await link_actor(session, verify_access_token(token))
    except InvalidAccessToken:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    actor_id = str(actor.id)
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
        await stream_manager.disconnect(ws)
    except Exception as e:
        logger.error("Voice WS error: %s", e)
        await stream_manager.disconnect(ws)
