"""Behaviour found by the launch load test (scripts/load_test.py).

- Rate limits key on the account, not only the IP: Indian carriers put many
  phones behind one carrier-NAT address.
- The in-process limiter table cannot grow without bound.
- A JWKS fetch never runs on the event loop.
- Collection routes answer directly instead of redirecting /workflows to
  /workflows/, which cost every list call from the app a second round trip.
"""
import time
import uuid

import pytest
from starlette.requests import Request

from app.config import settings
from app.core import oidc
from app.core.middleware import token_subject
from app.core.rate_limit import MemoryWindow
from tests.identity_tokens import mint_firebase_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _request(auth: str | None) -> Request:
    headers = [(b"authorization", auth.encode())] if auth is not None else []
    return Request({"type": "http", "headers": headers, "client": ("10.0.0.9", 1)})


def test_token_subject_reads_sub_without_verifying():
    token = mint_firebase_token(uid="user-123")
    assert token_subject(_request(f"Bearer {token}")) == "user-123"
    assert token_subject(_request(None)) is None
    assert token_subject(_request("Bearer not-a-jwt")) is None
    assert token_subject(_request("Bearer a.!!!.c")) is None
    assert token_subject(_request("Basic abc")) is None


@pytest.mark.asyncio
async def test_many_accounts_behind_one_ip_are_not_throttled_together(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    tokens = [mint_firebase_token(uid=f"nat-{uuid.uuid4().hex[:12]}") for _ in range(5)]
    for token in tokens:
        for _ in range(3):
            resp = await client.get("/auth/me", headers=_auth(token))
            assert resp.status_code == 200, resp.text

    # Each account still has its own limit.
    over = await client.get("/auth/me", headers=_auth(tokens[0]))
    assert over.status_code == 429
    assert over.headers["retry-after"] == "60"


@pytest.mark.asyncio
async def test_per_ip_ceiling_caps_forged_subjects(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_per_ip_per_minute", 4)
    statuses = []
    for _ in range(6):
        forged = mint_firebase_token(uid=f"forged-{uuid.uuid4().hex[:12]}")
        statuses.append((await client.get("/auth/me", headers=_auth(forged))).status_code)
    assert statuses[:4] == [200, 200, 200, 200]
    assert statuses[4:] == [429, 429]


def test_memory_window_sweeps_expired_keys(monkeypatch):
    window = MemoryWindow()
    for i in range(1000):
        assert window.allow(f"ip:1.2.3.4:/random/{i}", 5, 60)
    assert len(window._buckets) == 1000

    later = time.monotonic() + 120
    monkeypatch.setattr(time, "monotonic", lambda: later)
    window.allow("fresh", 5, 60)
    assert set(window._buckets) == {"fresh"}


def test_memory_window_resets_when_flooded(monkeypatch):
    monkeypatch.setattr(MemoryWindow, "MAX_KEYS", 50)
    window = MemoryWindow()
    for i in range(200):
        window.allow(f"k{i}", 5, 60)
    assert len(window._buckets) <= 51


@pytest.mark.asyncio
async def test_jwks_fetch_runs_off_the_event_loop(monkeypatch):
    import threading

    loop_thread = threading.get_ident()
    seen = {}

    def fake_verify(token, *, allow_network=True):
        if not allow_network:
            raise oidc._NetworkNeeded()
        seen["thread"] = threading.get_ident()
        return {"sub": "x"}

    monkeypatch.setattr(oidc, "verify_access_token", fake_verify)
    assert await oidc.verify_access_token_async("t") == {"sub": "x"}
    assert seen["thread"] != loop_thread


def test_cold_cache_asks_for_network_instead_of_fetching(monkeypatch):
    monkeypatch.setattr(oidc, "_test_jwks", None)
    oidc.clear_jwks_cache()

    def boom(*a, **k):
        raise AssertionError("fetched on the event loop")

    monkeypatch.setattr(oidc.httpx, "get", boom)
    with pytest.raises(oidc._NetworkNeeded):
        oidc._load_jwks("https://example.test/jwks", allow_network=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/workflows", "/actors", "/templates", "/capabilities"])
async def test_collections_answer_without_slash_redirect(client, path):
    token = mint_firebase_token(uid=f"slash-{uuid.uuid4().hex[:12]}")
    resp = await client.get(path, headers=_auth(token))
    assert resp.status_code not in (307, 308), resp.headers.get("location")


def test_websocket_token_prefers_the_header():
    assert oidc.websocket_token({"authorization": "Bearer abc.def.ghi"}, "old") == "abc.def.ghi"
    assert oidc.websocket_token({}, "from-query") == "from-query"
    assert oidc.websocket_token({"authorization": "Bearer "}, "from-query") == "from-query"
    assert oidc.websocket_token({}, "") == ""


@pytest.mark.asyncio
async def test_razorpay_routes_are_gone_without_razorpay(client, monkeypatch):
    """The app sells through Google Play; an unconfigured Razorpay must not hand out orders."""
    monkeypatch.setattr(settings, "use_fixtures", False)
    monkeypatch.setattr(settings, "razorpay_key_id", None)
    monkeypatch.setattr(settings, "razorpay_key_secret", None)
    token = mint_firebase_token(uid=f"rzp-{uuid.uuid4().hex[:12]}")
    create = await client.post("/onboarding/wallet/create-order", json={"plan_id": "personal"}, headers=_auth(token))
    assert create.status_code == 410
    initiate = await client.post("/payments/initiate", json={}, headers=_auth(token))
    assert initiate.status_code == 410
