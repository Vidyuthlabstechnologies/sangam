from __future__ import annotations
import json
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger("sangam.slack")


class SlackNotifier:
    def __init__(self):
        self._webhook_url = settings.slack_webhook_url or ""

    async def send_message(
        self,
        text: str,
        blocks: Optional[list[dict]] = None,
    ) -> bool:
        if not self._webhook_url:
            logger.warning("Slack not configured: no SLACK_WEBHOOK_URL")
            return False
        try:
            payload: dict = {"text": text}
            if blocks:
                payload["blocks"] = blocks
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self._webhook_url,
                    json=payload,
                )
                resp.raise_for_status()
                logger.info("Slack message sent")
                return True
        except Exception as e:
            logger.error("Slack send failed: %s", e)
            return False

    async def notify_workflow_event(
        self,
        event: str,
        workflow_name: str,
        workflow_id: str,
        initiator_name: str = "System",
    ) -> bool:
        colors = {
            "workflow_completed": "#2B9A6E",
            "workflow_failed": "#E74C3C",
            "approval_needed": "#E67E22",
            "payment_received": "#3B5BDB",
            "exception_raised": "#E74C3C",
            "sla_breach": "#E74C3C",
        }
        color = colors.get(event, "#888888")

        emoji = {
            "workflow_completed": "✅",
            "workflow_failed": "❌",
            "approval_needed": "👀",
            "payment_received": "💰",
            "exception_raised": "🚨",
            "sla_breach": "⏰",
        }.get(event, "🔔")

        titles = {
            "workflow_completed": "Workflow Completed",
            "workflow_failed": "Workflow Failed",
            "approval_needed": "Approval Required",
            "payment_received": "Payment Received",
            "exception_raised": "Exception Raised",
            "sla_breach": "SLA Breached",
        }
        title = titles.get(event, "Sangam Update")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} {title}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Workflow:*\n{workflow_name}"},
                    {"type": "mrkdwn", "text": f"*Initiator:*\n{initiator_name}"},
                ],
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Sangam"},
                        "url": f"{settings.app_url}/workflows/{workflow_id}",
                        "style": "primary",
                    },
                ],
            },
        ]

        return await self.send_message(f"{emoji} {title}: {workflow_name}", blocks)
