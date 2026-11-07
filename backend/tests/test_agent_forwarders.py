"""A recorded callback is forwarded to a Google Sheet and to staff on WhatsApp.

Forwarding is best-effort and runs after the webhook has already answered: a
down sheet or an expired WhatsApp token must never fail or delay the call the
agent is in the middle of. Nothing here talks to the real services; a fake
transport captures the requests.
"""
import json
import logging
import uuid

import httpx
import pytest

from app.config import settings
from app.core import agent_forwarders as fw

ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "call_id": "call-1",
    "caller_name": "Ravi Kumar",
    "caller_phone": "+919876543210",
    "service": "pan",
    "preferred_time": "tomorrow at 11",
    "language": "telugu",
    "urgency": "urgent",
    "notes": "PAN correction",
    "status": "new",
    "created_at": "2026-11-07T10:00:00",
}
TOKEN = "EAAB-super-secret-token"


@pytest.fixture
def seen(monkeypatch):
    """Capture outgoing requests instead of sending them."""
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        fw, "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True),
    )
    return captured


def _configure(monkeypatch, *, sheet=True, whatsapp=True):
    values = {
        "callback_sheet_webhook_url": "https://script.example.test/exec" if sheet else None,
        "callback_sheet_webhook_secret": "sheet-secret" if sheet else None,
        "whatsapp_phone_number_id": "1234567890" if whatsapp else None,
        "whatsapp_access_token": TOKEN if whatsapp else None,
        "whatsapp_staff_numbers": "919900000001, 919900000002" if whatsapp else None,
        "whatsapp_template_name": "surya_new_callback",
        "whatsapp_template_lang": "en",
        "whatsapp_graph_version": "v99.0",
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value, raising=False)


@pytest.mark.asyncio
async def test_nothing_is_sent_when_nothing_is_configured(monkeypatch, seen):
    _configure(monkeypatch, sheet=False, whatsapp=False)
    await fw.forward_callback(ROW)
    assert seen == []


@pytest.mark.asyncio
async def test_row_is_posted_to_the_sheet_with_its_secret(monkeypatch, seen):
    _configure(monkeypatch, whatsapp=False)
    await fw.forward_callback(ROW)

    assert len(seen) == 1
    req = seen[0]
    assert str(req.url) == "https://script.example.test/exec"
    body = json.loads(req.content)
    assert body["caller_phone"] == "+919876543210"
    assert body["secret"] == "sheet-secret"


@pytest.mark.asyncio
async def test_each_staff_number_gets_a_whatsapp_template_message(monkeypatch, seen):
    _configure(monkeypatch, sheet=False)
    await fw.forward_callback(ROW)

    assert len(seen) == 2
    assert {json.loads(r.content)["to"] for r in seen} == {"919900000001", "919900000002"}
    req = seen[0]
    assert str(req.url) == "https://graph.facebook.com/v99.0/1234567890/messages"
    assert req.headers["authorization"] == f"Bearer {TOKEN}"

    payload = json.loads(req.content)
    assert payload["messaging_product"] == "whatsapp"
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "surya_new_callback"
    params = payload["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == [
        "Ravi Kumar", "+919876543210", "pan", "tomorrow at 11", "urgent",
    ]


@pytest.mark.asyncio
async def test_a_failing_sheet_does_not_stop_whatsapp_or_raise(monkeypatch):
    _configure(monkeypatch)
    sent = []

    def handler(request):
        if "script.example.test" in str(request.url):
            return httpx.Response(500, text="boom")
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        fw, "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True),
    )

    await fw.forward_callback(ROW)  # must not raise

    assert len(sent) == 2


@pytest.mark.asyncio
async def test_network_errors_are_swallowed_and_the_token_is_never_logged(monkeypatch, caplog):
    _configure(monkeypatch)

    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    monkeypatch.setattr(
        fw, "_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True),
    )

    with caplog.at_level(logging.DEBUG):
        await fw.forward_callback(ROW)

    assert TOKEN not in caplog.text
    assert "sheet-secret" not in caplog.text


@pytest.mark.asyncio
async def test_the_webhook_forwards_a_new_callback_once(client, monkeypatch):
    calls = []

    async def spy(row):
        calls.append(row)

    monkeypatch.setattr("app.api.agent_callbacks.forward_callback", spy)
    monkeypatch.setattr(settings, "agent_webhook_secret", "hook-secret-0123456789", raising=False)
    body = {
        "caller_phone": "9876543210",
        "service": "pan",
        "call_id": f"call-{uuid.uuid4().hex[:10]}",
    }
    headers = {"X-Webhook-Secret": "hook-secret-0123456789"}

    first = await client.post("/agent-callbacks", json=body, headers=headers)
    retry = await client.post("/agent-callbacks", json=body, headers=headers)

    assert first.status_code == 201 and retry.status_code == 200
    assert len(calls) == 1
    assert calls[0]["caller_phone"] == "+919876543210"
