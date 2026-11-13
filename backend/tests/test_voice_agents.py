"""Sarvam Voice Agents (Samvaad) routes, in fixture mode.

What these pin: a business can only drive agents an admin bound to it; calls
need wallet credit; the unsigned outbound webhook is accepted only on its
per-call secret URL, is idempotent, and meters the wallet exactly once; the
live session proxy relays audio and transcripts without the key leaving the
server; and the live client speaks Samvaad's actual REST contract.
"""
import json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.billing_service import BillingService
from app.core.samvaad import SamvaadClient
from app.models.actor import Role
from app.models.samvaad import SamvaadAgentBinding, SamvaadCallAttempt
from app.models.sangamitra_release import WalletLedgerEntryModel
from tests.identity_tokens import login

pytestmark = pytest.mark.asyncio

APP_ID = "clinic-receptionist"


@pytest_asyncio.fixture
async def tenant(current_actor, db_session):
    """The caller's own business, with Rs 100 of call credit and one bound agent."""
    tid = str(current_actor.id)
    wallet = await BillingService(db_session).get_or_create_wallet(
        tid, owner_actor_id=current_actor.id, business_name="Clinic"
    )
    wallet.call_balance_paise = 10_000
    wallet.deployment_status = "ACTIVE"
    db_session.add(
        SamvaadAgentBinding(
            tenant_id=tid,
            app_id=APP_ID,
            app_version=2,
            label="Front desk",
            connection_id="conn-exotel-001",
            agent_phone_number="+918047168000",
        )
    )
    await db_session.commit()
    return tid


@pytest_asyncio.fixture
async def admin(current_actor, db_session):
    current_actor.roles = [Role.ADMIN]
    await db_session.commit()
    return current_actor


def _webhook_token_from(monkeypatch):
    """Capture the webhook URL the client is asked to register with Samvaad."""
    seen = {}
    real = SamvaadClient.create_outbound_call

    async def spy(self, **kwargs):
        seen.update(kwargs)
        return await real(self, **kwargs)

    monkeypatch.setattr(SamvaadClient, "create_outbound_call", spy)
    return seen


# ------------------------------------------------------------------ bindings


async def test_status_never_reveals_the_key(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_samvaad_api_key", "sk_live_should_not_leak")
    r = await client.get("/voice-agents/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["mode"] == "fixture"  # tests force fixtures
    assert "sk_live" not in r.text


async def test_only_admins_bind_agents(client, auth_headers, current_actor):
    body = {"tenant_id": str(current_actor.id), "app_id": APP_ID}
    r = await client.put("/voice-agents/bindings", json=body, headers=auth_headers)
    assert r.status_code == 403


async def test_admin_binds_an_agent_and_owner_sees_it(client, auth_headers, admin):
    body = {
        "tenant_id": str(admin.id),
        "app_id": APP_ID,
        "app_version": 3,
        "label": "Front desk",
        "connection_id": "conn-1",
        "agent_phone_number": "+918047168000",
    }
    r = await client.put("/voice-agents/bindings", json=body, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["can_call_out"] is True
    # Upsert: the second PUT updates rather than duplicating.
    r = await client.put("/voice-agents/bindings", json={**body, "app_version": 4}, headers=auth_headers)
    assert r.json()["app_version"] == 4
    agents = (await client.get("/voice-agents/agents", headers=auth_headers)).json()
    assert [a["app_version"] for a in agents] == [4]


# ------------------------------------------------------------------ outbound


async def test_outbound_call_is_queued_and_number_is_masked(client, auth_headers, tenant, monkeypatch):
    seen = _webhook_token_from(monkeypatch)
    r = await client.post(
        "/voice-agents/calls",
        json={"app_id": APP_ID, "user_phone_number": "+91 98765-43210", "initial_language_name": "Kannada"},
        headers=auth_headers,
    )
    assert r.status_code == 202, r.text
    call = r.json()
    assert call["status"] == "queued"
    assert call["attempt_id"].startswith("fixture-")
    assert call["user_phone"] == "+91******3210"
    assert seen["user_phone_number"] == "+919876543210"
    assert seen["connection_id"] == "conn-exotel-001"
    assert seen["overrides"] == {"initial_language_name": "Kannada"}
    assert "/voice-agents/webhooks/outbound/" in seen["webhook_url"]


async def test_cannot_call_with_an_agent_bound_to_someone_else(client, auth_headers, tenant, db_session):
    db_session.add(SamvaadAgentBinding(tenant_id="other-biz", app_id="their-agent", app_version=1,
                                       connection_id="c", agent_phone_number="+918000000001"))
    await db_session.commit()
    r = await client.post(
        "/voice-agents/calls",
        json={"app_id": "their-agent", "user_phone_number": "+919876543210"},
        headers=auth_headers,
    )
    assert r.status_code == 404
    r = await client.post(
        "/voice-agents/calls",
        json={"app_id": "their-agent", "user_phone_number": "+919876543210", "tenant_id": "other-biz"},
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_no_credit_no_call(client, auth_headers, tenant, db_session):
    wallet = await BillingService(db_session).get_wallet(tenant)
    wallet.call_balance_paise = 0
    await db_session.commit()
    r = await client.post(
        "/voice-agents/calls", json={"app_id": APP_ID, "user_phone_number": "+919876543210"}, headers=auth_headers
    )
    assert r.status_code == 402


async def test_rejects_non_e164_numbers(client, auth_headers, tenant):
    r = await client.post(
        "/voice-agents/calls", json={"app_id": APP_ID, "user_phone_number": "9876543210"}, headers=auth_headers
    )
    assert r.status_code == 422


async def test_pending_call_cap(client, auth_headers, tenant, monkeypatch):
    monkeypatch.setattr(settings, "samvaad_max_pending_calls", 2)
    body = {"app_id": APP_ID, "user_phone_number": "+919876543210"}
    for _ in range(2):
        assert (await client.post("/voice-agents/calls", json=body, headers=auth_headers)).status_code == 202
    assert (await client.post("/voice-agents/calls", json=body, headers=auth_headers)).status_code == 429


async def test_webhook_completes_call_meters_once_and_rejects_forgeries(
    client, auth_headers, tenant, db_session, monkeypatch
):
    seen = _webhook_token_from(monkeypatch)
    call = (await client.post(
        "/voice-agents/calls", json={"app_id": APP_ID, "user_phone_number": "+919876543210"}, headers=auth_headers
    )).json()
    hook_path = httpx.URL(seen["webhook_url"]).path
    payload = {
        "attempt_id": call["attempt_id"],
        "status": "connected",
        "channel_info": {"channel_type": "v2v", "channel_provider": "exotel", "agent_phone_number": "+918047168000"},
        "app_id": APP_ID,
        "app_version": 2,
        "duration": 61.2,
        "interaction_id": "20261112/abc-123",
        "failure_reason": None,
        "final_agent_variables": {"appointment": "tomorrow 11am"},
        "webhook_config": {"url": seen["webhook_url"], "metadata": {"call_id": call["id"]}},
        "interaction_transcript": [
            {"role": "agent", "en_text": "Hello, which day suits you?"},
            {"role": "user", "en_text": "Tomorrow at eleven."},
        ],
    }

    # Wrong token, and right token with someone else's attempt id: both refused.
    bad = hook_path.rsplit("/", 1)[0] + "/" + "x" * 43
    assert (await client.post(bad, json=payload)).status_code == 404
    assert (await client.post(hook_path, json={**payload, "attempt_id": "forged"})).status_code == 404

    before = (await BillingService(db_session).get_wallet(tenant)).call_balance_paise
    r = await client.post(hook_path, json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["billed_inr"] > 0
    # Samvaad retries: no second debit.
    assert (await client.post(hook_path, json=payload)).json()["duplicate"] is True

    wallet = await BillingService(db_session).get_wallet(tenant)
    await db_session.refresh(wallet)
    after = wallet.call_balance_paise
    assert after < before
    entries = (await db_session.execute(
        select(WalletLedgerEntryModel).where(WalletLedgerEntryModel.tenant_id == tenant,
                                             WalletLedgerEntryModel.kind == "CALL_USAGE")
    )).scalars().all()
    assert len(entries) == 1

    got = (await client.get(f"/voice-agents/calls/{call['id']}", headers=auth_headers)).json()
    assert got["status"] == "connected"
    assert got["final_agent_variables"] == {"appointment": "tomorrow 11am"}
    transcript = (await client.get(f"/voice-agents/calls/{call['id']}/transcript", headers=auth_headers)).json()
    assert transcript["interaction_id"] == "20261112/abc-123"
    assert transcript["messages"][0]["role"] == "agent"


async def test_unanswered_call_is_not_billed(client, auth_headers, tenant, db_session, monkeypatch):
    seen = _webhook_token_from(monkeypatch)
    call = (await client.post(
        "/voice-agents/calls", json={"app_id": APP_ID, "user_phone_number": "+919876543210"}, headers=auth_headers
    )).json()
    r = await client.post(
        httpx.URL(seen["webhook_url"]).path,
        json={"attempt_id": call["attempt_id"], "status": "no_answer", "duration": None},
    )
    assert r.json()["billed_inr"] is None
    row = await db_session.get(SamvaadCallAttempt, uuid.UUID(call["id"]))
    await db_session.refresh(row)
    assert row.status == "no_answer"


async def test_other_users_cannot_read_my_calls(client, auth_headers, tenant, monkeypatch):
    call = (await client.post(
        "/voice-agents/calls", json={"app_id": APP_ID, "user_phone_number": "+919876543210"}, headers=auth_headers
    )).json()
    from app.api.dependencies import get_current_actor
    from app.main import app

    app.dependency_overrides.pop(get_current_actor, None)
    token, _ = await login(client, name="Stranger")
    r = await client.get(f"/voice-agents/calls/{call['id']}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


# ------------------------------------------------------------------ admin


async def test_admin_workspace_routes_in_fixture_mode(client, auth_headers, admin):
    assert (await client.get("/voice-agents/deployments", headers=auth_headers)).status_code == 200
    r = await client.put("/voice-agents/deployments/dep-1/status", json={"action": "pause"}, headers=auth_headers)
    assert r.json()["status"] == "paused"
    r = await client.get(f"/voice-agents/interactions?app_id={APP_ID}", headers=auth_headers)
    assert r.status_code == 200 and r.json()["items"]
    r = await client.get(
        f"/voice-agents/interactions/transcript?app_id={APP_ID}&interaction_id=20261101/x", headers=auth_headers
    )
    assert r.json()["messages"][0]["role"] == "agent"


async def test_workspace_routes_are_admin_only(client, auth_headers):
    for path in ("/voice-agents/deployments", f"/voice-agents/interactions?app_id={APP_ID}"):
        assert (await client.get(path, headers=auth_headers)).status_code == 403


# ------------------------------------------------------------------ live client contract


async def test_live_client_matches_samvaad_rest_contract(monkeypatch):
    """With a key, the client hits the documented URLs with X-API-Key and the documented bodies."""
    monkeypatch.setattr(settings, "use_fixtures", False)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/outbounds"):
            return httpx.Response(200, json={"attempt_id": "att-1"})
        if "/transcripts/" in request.url.path:
            return httpx.Response(200, json={"interaction_id": "x", "messages": []})
        return httpx.Response(200, json={"ok": True})

    c = SamvaadClient(api_key="va-key", org_id="org1", workspace_id="ws1", transport=httpx.MockTransport(handler))
    assert not c.use_fixtures
    attempt = await c.create_outbound_call(
        app_id="a1", app_version=2, connection_id="conn", agent_phone_number="+918000000000",
        user_phone_number="+919800000000", webhook_url="https://api.example/hook/t",
    )
    assert attempt == "att-1"
    await c.get_transcript("a1", "20261007/9f1c")
    await c.update_deployment_status("dep-1", "resume")

    out, tr, st = calls
    assert out.method == "POST"
    assert str(out.url) == "https://apps.sarvam.ai/api/outbounds/v1/orgs/org1/workspaces/ws1/outbounds"
    assert out.headers["X-API-Key"] == "va-key"
    assert "api-subscription-key" not in out.headers
    body = json.loads(out.content)
    assert body["app_config"]["connection_config"] == {"connection_id": "conn", "agent_phone_number": "+918000000000"}
    assert body["user_config"] == {"user_phone_number": "+919800000000"}
    assert body["webhook_config"]["url"] == "https://api.example/hook/t"
    assert tr.url.path == "/api/analytics/v1/org1/ws1/a1/transcripts/20261007/9f1c"
    assert st.method == "PUT" and json.loads(st.content) == {"action": "resume"}


async def test_live_mode_without_workspace_is_503(client, auth_headers, tenant, monkeypatch):
    monkeypatch.setattr(settings, "use_fixtures", False)
    monkeypatch.setattr(settings, "sarvam_samvaad_api_key", "va-key")
    monkeypatch.setattr(settings, "samvaad_org_id", None)
    r = await client.post(
        "/voice-agents/calls", json={"app_id": APP_ID, "user_phone_number": "+919876543210"}, headers=auth_headers
    )
    assert r.status_code == 503


async def test_upstream_auth_failure_is_a_502_not_a_401(monkeypatch):
    monkeypatch.setattr(settings, "use_fixtures", False)
    transport = httpx.MockTransport(lambda req: httpx.Response(401, json={"detail": "bad key"}))
    c = SamvaadClient(api_key="wrong", org_id="o", workspace_id="w", transport=transport)
    with pytest.raises(Exception) as exc:
        await c.list_deployments()
    assert exc.value.status_code == 502


# ------------------------------------------------------------------ live session proxy


async def test_live_session_proxy_relays_audio_and_text(client):
    """End to end over a real WebSocket against the fixture agent."""
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.main import app
    from tests.conftest import TEST_DATABASE_URL

    token, actor_id = await login(client, name="Owner")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        wallet = await BillingService(s).get_or_create_wallet(actor_id, owner_actor_id=uuid.UUID(actor_id))
        wallet.call_balance_paise = 10_000
        wallet.deployment_status = "ACTIVE"
        s.add(SamvaadAgentBinding(tenant_id=actor_id, app_id=APP_ID, app_version=None))
        await s.commit()
    await engine.dispose()

    # The TestClient runs the app on its own event loop, so it needs its own engine.
    async def fresh_session():
        eng = create_async_engine(TEST_DATABASE_URL)
        async with async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)() as sess:
            yield sess
        await eng.dispose()

    app.dependency_overrides[get_session] = fresh_session
    with TestClient(app) as tc:
        with tc.websocket_connect(f"/voice-agents/ws/{APP_ID}?token={token}") as ws:
            assert ws.receive_json()["event"] == "interaction_connected"
            greeting = ws.receive_json()
            assert greeting == {"type": "transcript", "role": "agent", "content": greeting["content"]}
            assert ws.receive_json() == {"type": "audio_format", "encoding": "pcm_s16le", "sample_rate": 16000}
            assert len(ws.receive_bytes()) == 3200
            assert ws.receive_json()["type"] == "ready"

            ws.send_bytes(b"\x00\x00" * 16000)  # one second of audio = one fixture turn
            assert ws.receive_json()["role"] == "user"
            assert ws.receive_json()["role"] == "agent"
            ws.receive_bytes()

            ws.send_text(json.dumps({"type": "text", "text": "Book me for Friday"}))
            assert ws.receive_json() == {"type": "transcript", "role": "user", "content": "Book me for Friday"}
            ws.receive_json()
            ws.receive_bytes()

            ws.send_text(json.dumps({"type": "end"}))
            ended = ws.receive_json()
            assert ended["type"] == "ended" and ended["reason"] == "client_ended"

        with tc.websocket_connect(f"/voice-agents/ws/not-my-agent?token={token}") as ws:
            assert ws.receive_json()["status"] == 404


async def test_live_session_uses_the_sdk_with_the_server_key(monkeypatch):
    """Live mode builds a headless AsyncSamvaadAgent; nothing connects until start()."""
    from app.core.samvaad import _SdkSession, open_voice_session

    monkeypatch.setattr(settings, "use_fixtures", False)
    monkeypatch.setattr(settings, "sarvam_samvaad_api_key", "va-key")
    monkeypatch.setattr(settings, "samvaad_org_id", "org1")
    monkeypatch.setattr(settings, "samvaad_workspace_id", "ws1")

    async def noop(*_a, **_k):
        return None

    session = open_voice_session(
        app_id="a1", app_version=3, user_identifier="t:u", on_transcript=noop, on_audio=noop, on_event=noop,
        initial_language_name="Kannada",
    )
    assert isinstance(session, _SdkSession)
    agent = session._agent
    assert agent.api_key.get_secret_value() == "va-key"
    assert agent.audio_interface is None  # headless: audio comes from the phone via the proxy
    assert agent.config.version == 3 and agent.config.sample_rate == 16000
    assert agent._construct_url() == "https://apps.sarvam.ai/api/app-runtime/orgs/org1/workspaces/ws1/apps/a1/url"
