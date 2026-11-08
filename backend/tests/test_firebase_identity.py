"""Firebase ID tokens from the Android app. Signed locally; nothing is fetched."""
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.config import settings
from app.core import oidc
from app.models.actor import Actor
from tests.identity_tokens import mint_firebase_token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_google_sign_in_creates_actor_in_personal_workspace(client, db_session):
    uid = f"g-{uuid.uuid4().hex[:20]}"
    token = mint_firebase_token(uid=uid, email="asha@example.test", name="Asha")

    first = await client.get("/auth/me", headers=_auth(token))
    second = await client.get("/auth/me", headers=_auth(token))

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["name"] == "Asha"
    assert body["email"] == "asha@example.test"
    assert body["organization_id"] == f"fb-{uid}"
    assert second.json()["actor_id"] == body["actor_id"]

    rows = (await db_session.execute(select(Actor).where(Actor.zitadel_sub == uid))).scalars().all()
    assert len(rows) == 1
    assert rows[0].password_hash is None


@pytest.mark.asyncio
async def test_email_password_user_can_use_the_api(client):
    uid = f"p-{uuid.uuid4().hex[:20]}"
    token = mint_firebase_token(uid=uid, provider="password", email_verified=False, name="Ravi")

    me = await client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200, me.text
    # An unverified address is not stored as the actor's email.
    assert me.json()["email"] is None

    workflows = await client.get("/workflows/", headers=_auth(token))
    assert workflows.status_code == 200, workflows.text


@pytest.mark.asyncio
async def test_unverified_email_rejected_when_required(client, monkeypatch):
    monkeypatch.setattr(settings, "firebase_require_verified_email", True)
    token = mint_firebase_token(uid=f"p-{uuid.uuid4().hex[:20]}", provider="password", email_verified=False)
    assert (await client.get("/auth/me", headers=_auth(token))).status_code == 401

    verified = mint_firebase_token(uid=f"p-{uuid.uuid4().hex[:20]}", provider="password", email_verified=True)
    assert (await client.get("/auth/me", headers=_auth(verified))).status_code == 200


@pytest.mark.asyncio
async def test_token_cannot_choose_its_workspace(client):
    uid = f"g-{uuid.uuid4().hex[:20]}"
    token = mint_firebase_token(
        uid=uid,
        extra={
            "org_id": "victim-org",
            "urn:zitadel:iam:org:id": "victim-org",
            "urn:zitadel:iam:user:resourceowner:id": "victim-org",
        },
    )
    me = await client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["organization_id"] == f"fb-{uid}"


@pytest.mark.asyncio
async def test_two_firebase_users_do_not_see_each_others_workflows(client):
    alice = mint_firebase_token(uid=f"a-{uuid.uuid4().hex[:20]}", name="Alice")
    bob = mint_firebase_token(uid=f"b-{uuid.uuid4().hex[:20]}", name="Bob")
    alice_me = (await client.get("/auth/me", headers=_auth(alice))).json()

    created = await client.post(
        "/workflows/",
        headers=_auth(alice),
        json={"name": "Alice only", "initiator_id": alice_me["actor_id"]},
    )
    assert created.status_code in (200, 201), created.text

    bob_list = await client.get("/workflows/", headers=_auth(bob))
    assert bob_list.status_code == 200
    names = [w.get("name") for w in bob_list.json()] if isinstance(bob_list.json(), list) else []
    assert "Alice only" not in names


@pytest.mark.parametrize(
    "kwargs",
    [
        {"audience": "some-other-project"},
        {"provider": "anonymous"},
        {"provider": "custom"},
        {"expires_in": -3600},
        {"auth_time_offset": 3600},
        {"key": "other"},
    ],
    ids=["wrong-audience", "anonymous", "custom-token", "expired", "future-auth-time", "forged-signature"],
)
@pytest.mark.asyncio
async def test_bad_firebase_tokens_are_rejected(client, kwargs):
    if kwargs.get("key") == "other":
        kwargs = {**kwargs, "key": rsa.generate_private_key(public_exponent=65537, key_size=2048)}
    token = mint_firebase_token(uid=f"x-{uuid.uuid4().hex[:20]}", **kwargs)
    assert (await client.get("/auth/me", headers=_auth(token))).status_code == 401


@pytest.mark.asyncio
async def test_firebase_tokens_rejected_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "firebase_project_id", None)
    token = mint_firebase_token(uid=f"x-{uuid.uuid4().hex[:20]}")
    assert (await client.get("/auth/me", headers=_auth(token))).status_code == 401


def test_jwks_is_cached_and_refetched_on_unknown_kid(monkeypatch):
    calls = []
    key = {"kty": "RSA", "kid": "k1", "n": "x", "e": "AQAB"}

    class _Response:
        def __init__(self, keys):
            self._keys = keys

        def raise_for_status(self):
            return None

        def json(self):
            return {"keys": self._keys}

    def fake_get(url, timeout):
        calls.append(url)
        return _Response([key] if len(calls) == 1 else [key, {**key, "kid": "k2"}])

    oidc.install_test_jwks(None)
    try:
        monkeypatch.setattr(oidc.httpx, "get", fake_get)
        monkeypatch.setattr(oidc, "_JWKS_MIN_REFRESH_SECONDS", 0)
        url = "https://jwks.test/keys"
        assert oidc._select_key("k1", url)["kid"] == "k1"
        assert oidc._select_key("k1", url)["kid"] == "k1"
        assert len(calls) == 1  # served from cache
        assert oidc._select_key("k2", url)["kid"] == "k2"
        assert len(calls) == 2  # rotation picked up
    finally:
        from tests.identity_tokens import install

        install()
