from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.actor import Actor

logger = logging.getLogger("sangam.notifications")

FCM_BASE = "https://fcm.googleapis.com/v1"
FCM_SEND_URL = f"{FCM_BASE}/projects/{{project_id}}/messages:send"


@dataclass
class NotificationPayload:
    title: str
    body: str
    data: Optional[Dict[str, str]] = None
    workflow_id: Optional[str] = None
    actor_id: Optional[str] = None
    notification_type: str = "general"


def _to_uuid(val: str) -> UUID:
    return UUID(val) if isinstance(val, str) else val


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_fcm_tokens(self, actor_id: str) -> List[str]:
        result = await self.session.execute(
            select(Actor).where(Actor.id == _to_uuid(actor_id))
        )
        actor = result.scalar_one_or_none()
        if not actor:
            return []
        tokens = (actor.extra_attributes or {}).get("fcm_tokens", [])
        if isinstance(tokens, list):
            return tokens
        return []

    async def register_fcm_token(self, actor_id: str, token: str) -> None:
        result = await self.session.execute(
            select(Actor).where(Actor.id == _to_uuid(actor_id))
        )
        actor = result.scalar_one_or_none()
        if not actor:
            raise ValueError("Actor not found")
        attrs = actor.extra_attributes or {}
        tokens = attrs.get("fcm_tokens", [])
        if not isinstance(tokens, list):
            tokens = []
        if token not in tokens:
            tokens.append(token)
        attrs["fcm_tokens"] = tokens
        actor.extra_attributes = attrs
        await self.session.commit()

    async def send_to_actor(
        self,
        actor_id: str,
        payload: NotificationPayload,
    ) -> int:
        tokens = await self.get_fcm_tokens(actor_id)
        sent = 0
        for token in tokens:
            try:
                await self._send_fcm(token, payload)
                sent += 1
            except Exception as e:
                logger.error("FCM send failed for actor %s token %s: %s", actor_id, token[:16], e)
        return sent

    async def send_to_multiple(
        self,
        actor_ids: List[str],
        payload: NotificationPayload,
    ) -> int:
        total = 0
        for aid in actor_ids:
            total += await self.send_to_actor(aid, payload)
        return total

    async def broadcast(
        self,
        payload: NotificationPayload,
        role_filter: Optional[str] = None,
    ) -> int:
        query = select(Actor).where(Actor.is_active == True)
        if role_filter:
            result = await self.session.execute(query)
            actors = result.scalars().all()
            actors = [a for a in actors if role_filter in (a.roles or [])]
        else:
            result = await self.session.execute(query)
            actors = result.scalars().all()
        total = 0
        for actor in actors:
            total += await self.send_to_actor(str(actor.id), payload)
        return total

    async def _send_fcm(self, token: str, payload: NotificationPayload) -> None:
        if not settings.fcm_server_key:
            logger.warning("FCM not configured: no server key")
            return
        message = {
            "token": token,
            "notification": {
                "title": payload.title,
                "body": payload.body,
            },
        }
        if payload.data:
            message["data"] = payload.data
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                FCM_SEND_URL.format(project_id=settings.fcm_project_id),
                headers={
                    "Authorization": f"key={settings.fcm_server_key}",
                    "Content-Type": "application/json",
                },
                json={"message": message},
            )
            if response.status_code == 404:
                logger.warning("FCM token invalid, should remove: %s...", token[:16])
                raise ValueError("Invalid token")
            response.raise_for_status()


async def notify_workflow_event(
    session: AsyncSession,
    actor_ids: List[str],
    event: str,
    workflow_name: str,
    workflow_id: str,
) -> int:
    titles = {
        "approval_needed": "Approval Required",
        "workflow_completed": "Workflow Completed",
        "workflow_failed": "Workflow Failed",
        "phase_changed": "Phase Updated",
        "payment_received": "Payment Received",
        "new_handoff": "Handoff Received",
        "exception_raised": "Exception Raised",
        "sla_warning": "SLA Warning",
        "sla_breach": "SLA Breached",
    }
    title = titles.get(event, "Sangam Update")
    body_map = {
        "approval_needed": f"Your approval is needed for '{workflow_name}'",
        "workflow_completed": f"Workflow '{workflow_name}' completed successfully",
        "workflow_failed": f"Workflow '{workflow_name}' has failed",
        "phase_changed": f"Workflow '{workflow_name}' moved to next phase",
        "payment_received": f"Payment received for '{workflow_name}'",
        "new_handoff": f"A handoff has been assigned to you in '{workflow_name}'",
        "exception_raised": f"An exception occurred in '{workflow_name}'",
        "sla_warning": f"SLA warning: '{workflow_name}' approaching deadline",
        "sla_breach": f"SLA breached for '{workflow_name}'",
    }
    body = body_map.get(event, f"Update on workflow '{workflow_name}'")
    ns = NotificationService(session)
    return await ns.send_to_multiple(
        actor_ids,
        NotificationPayload(
            title=title,
            body=body,
            data={
                "workflow_id": workflow_id,
                "event": event,
                "type": "workflow_update",
            },
            workflow_id=workflow_id,
            notification_type=event,
        ),
    )
