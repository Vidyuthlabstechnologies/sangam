from __future__ import annotations
import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.config import settings

logger = logging.getLogger("sangam.email")


def deliver_smtp(message: EmailMessage) -> None:
    """Send one message with the stdlib SMTP client. No third-party mail SDK."""
    host = settings.smtp_host or ""
    with smtplib.SMTP(host, settings.smtp_port, timeout=15) as smtp:
        smtp.ehlo()
        if settings.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


class EmailService:
    def __init__(self):
        self._from_email = settings.email_from or "noreply@sangam.ai"
        self._from_name = settings.email_from_name or "Sangam"

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        if not (settings.smtp_host or "").strip():
            logger.warning("Email not configured: no SMTP_HOST")
            return False

        message = EmailMessage()
        message["From"] = f"{self._from_name} <{self._from_email}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body or "")
        if html_body:
            message.add_alternative(html_body, subtype="html")

        try:
            await asyncio.to_thread(deliver_smtp, message)
        except Exception as exc:
            logger.error("Email send failed: %s", type(exc).__name__)
            return False
        logger.info("Email sent: %s", subject)
        return True

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
