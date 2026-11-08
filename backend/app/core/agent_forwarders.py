"""Forward a recorded voice-agent callback to a Google Sheet and to WhatsApp.

Best effort, run after the webhook has answered: a down sheet or an expired
WhatsApp token must never fail or slow the call the agent is in. Each target is
optional and silently skipped when its settings are absent.

Only error types and HTTP status codes are logged. Request bodies and headers
hold the access token, the sheet secret and callers' phone numbers, so they
are never written to logs.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

import httpx

from app.config import settings

__all__ = ["forward_callback"]

logger = logging.getLogger("sangam.agent_forwarders")

_TIMEOUT_SECONDS = 10.0


def _client() -> httpx.AsyncClient:
    # Apps Script web apps answer a POST with a redirect, so follow it.
    return httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=True)


def _describe(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


def _staff_numbers() -> List[str]:
    digits = (re.sub(r"\D", "", n) for n in (settings.whatsapp_staff_numbers or "").split(","))
    return [d for d in digits if d]


async def _to_sheet(row: Dict[str, Any]) -> None:
    url = settings.callback_sheet_webhook_url
    if not url:
        return
    # Apps Script cannot read request headers, so the secret travels in the body.
    payload = {**row, "secret": settings.callback_sheet_webhook_secret}
    async with _client() as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def _to_whatsapp(row: Dict[str, Any]) -> None:
    s = settings
    numbers = _staff_numbers()
    if not (s.whatsapp_phone_number_id and s.whatsapp_access_token and s.whatsapp_graph_version and numbers):
        return

    url = f"https://graph.facebook.com/{s.whatsapp_graph_version}/{s.whatsapp_phone_number_id}/messages"
    # Order must match the placeholders in the approved template body.
    values = [
        row.get("caller_name") or "Unknown",
        row["caller_phone"],
        row["service"],
        row.get("preferred_time") or "not given",
        row["urgency"],
    ]
    headers = {"Authorization": f"Bearer {s.whatsapp_access_token}"}

    async def send(client: httpx.AsyncClient, to: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": s.whatsapp_template_name,
                "language": {"code": s.whatsapp_template_lang},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": v} for v in values]}
                ],
            },
        }
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()

    async with _client() as client:
        results = await asyncio.gather(*(send(client, n) for n in numbers), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("WhatsApp notification failed (%s)", _describe(result))


async def forward_callback(row: Dict[str, Any]) -> None:
    """Send `row` to every configured target (Sheet, WhatsApp). Never raises."""
    outcomes = await asyncio.gather(_to_sheet(row), _to_whatsapp(row), return_exceptions=True)
    for name, outcome in zip(("sheet", "whatsapp"), outcomes):
        if isinstance(outcome, BaseException):
            logger.warning("Forwarding to %s failed (%s)", name, _describe(outcome))
