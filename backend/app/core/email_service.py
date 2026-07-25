from __future__ import annotations
import logging
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx

from app.config import settings

logger = logging.getLogger("sangam.email")


class EmailService:
    def __init__(self):
        self._api_key = settings.email_api_key or ""
        self._from_email = settings.email_from or "noreply@sangam.ai"
        self._from_name = settings.email_from_name or "Sangam"

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        if not self._api_key:
            logger.warning("Email not configured: no EMAIL_API_KEY")
            return False

        try:
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": self._from_email, "name": self._from_name},
                "subject": subject,
                "content": [
                    {
                        "type": "text/html",
                        "value": html_body,
                    }
                ],
            }
            if text_body:
                payload["content"].append({
                    "type": "text/plain",
                    "value": text_body,
                })

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                logger.info("Email sent to %s: %s", to_email, subject)
                return True
        except Exception as e:
            logger.error("Email send failed to %s: %s", to_email, e)
            return False

    async def send_workflow_notification(
        self,
        to_email: str,
        actor_name: str,
        event: str,
        workflow_name: str,
        workflow_id: str,
    ) -> bool:
        titles = {
            "approval_needed": "Approval Required",
            "workflow_completed": "Workflow Completed",
            "workflow_failed": "Workflow Failed",
            "payment_received": "Payment Received",
        }
        title = titles.get(event, "Sangam Update")

        body_text = {
            "approval_needed": f"A workflow requires your approval: {workflow_name}",
            "workflow_completed": f"Workflow completed successfully: {workflow_name}",
            "workflow_failed": f"Workflow has failed: {workflow_name}",
            "payment_received": f"Payment received for: {workflow_name}",
        }.get(event, f"Update on workflow: {workflow_name}")

        html = f"""<html><body style="font-family:sans-serif;padding:24px;max-width:600px">
<h2 style="color:#3B5BDB;">{title}</h2>
<p>Hi {actor_name},</p>
<p>{body_text}</p>
<p style="margin-top:24px">
<a href="{settings.app_url or 'http://localhost:5173'}/workflows/{workflow_id}"
   style="background:#3B5BDB;color:white;padding:10px 20px;border-radius:6px;text-decoration:none">
  View Workflow
</a>
</p>
<hr style="margin-top:32px;border:none;border-top:1px solid #eee"/>
<p style="color:#888;font-size:12px">Sangam Workflow Platform</p>
</body></html>"""

        return await self.send(to_email, title, html, body_text)
