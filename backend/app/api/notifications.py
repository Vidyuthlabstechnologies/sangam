from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.api.dependencies import get_current_actor
from app.models.actor import Actor
from app.core.notifications import NotificationService, NotificationPayload

router = APIRouter(prefix="/notifications", tags=["notifications"])


class RegisterFCMTokenRequest(BaseModel):
    token: str


class SendNotificationRequest(BaseModel):
    actor_id: str
    title: str
    body: str
    data: Optional[dict] = None


@router.post("/fcm/register")
async def register_fcm_token(
    request: RegisterFCMTokenRequest,
    current_actor: Actor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    ns = NotificationService(session)
    await ns.register_fcm_token(str(current_actor.id), request.token)
    return {"status": "ok"}


@router.get("/devices")
async def list_devices(
    current_actor: Actor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    ns = NotificationService(session)
    tokens = await ns.get_fcm_tokens(str(current_actor.id))
    return {"tokens": tokens}


@router.post("/test")
async def test_notification(
    request: SendNotificationRequest,
    current_actor: Actor = Depends(get_current_actor),
    session: AsyncSession = Depends(get_session),
):
    if request.actor_id != str(current_actor.id):
        raise HTTPException(status_code=403, detail="Cannot send a test notification to another actor")
    ns = NotificationService(session)
    sent = await ns.send_to_actor(
        str(current_actor.id),
        NotificationPayload(
            title=request.title,
            body=request.body,
            data=request.data,
            notification_type="test",
        ),
    )
    return {"sent": sent}
