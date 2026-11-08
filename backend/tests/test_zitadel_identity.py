"""Zitadel access tokens are the only way in. Tests sign locally and never call the network."""
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from app.config import settings
from app.core.oidc import InvalidAccessToken, install_test_jwks, verify_access_token
from app.models.actor import Actor
from tests.identity_tokens import TEST_ISSUER, mint_access_token


@pytest.mark.asyncio
async def test_missing_and_invalid_tokens_are_rejected(client):
    missing = await client.get("/workflows/")
    assert missing.status_code == 401

    garbage = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert garbage.status_code == 401

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = mint_access_token(sub="intruder", organization_id="org-a", key=other_key)
    bad_sig = await client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert bad_sig.status_code == 401

    hmac = jwt.encode(
        {"sub": "intruder", "iss": TEST_ISSUER, "aud": "sangam-test-web", "exp": 9_999_999_999},
        "local-secret",
        algorithm="HS256",
    )
    local = await client.get("/auth/me", headers={"Authorization": f"Bearer {hmac}"})
    assert local.status_code == 401

    no_org = mint_access_token(sub="no-org", include_org=False)
    rejected = await client.get("/auth/me", headers={"Authorization": f"Bearer {no_org}"})
    assert rejected.status_code == 401


@pytest.mark.asyncio
async def test_jit_links_one_actor_and_stores_no_password(client, db_session):
    subject = f"zitadel-{uuid.uuid4().hex}"
    token = mint_access_token(
        sub=subject,
        organization_id="org-alpha",
        name="Ada Lovelace",
        email="ada@example.test",
    )
    headers = {"Authorization": f"Bearer {token}"}
    first = await client.get("/auth/me", headers=headers)
    second = await client.get("/auth/me", headers=headers)
    assert first.status_code == 200
    assert first.json()["actor_id"] == second.json()["actor_id"]
    assert first.json()["organization_id"] == "org-alpha"

    rows = (
        await db_session.execute(select(Actor).where(Actor.zitadel_sub == subject))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].password_hash is None
    assert rows[0].zitadel_org_id == "org-alpha"
    assert rows[0].email == "ada@example.test"

    other_org = mint_access_token(sub=subject, organization_id="org-beta", name="Ada Lovelace")
    moved = await client.get("/auth/me", headers={"Authorization": f"Bearer {other_org}"})
    assert moved.status_code == 200
    assert moved.json()["actor_id"] != first.json()["actor_id"]
    assert moved.json()["organization_id"] == "org-beta"


@pytest.mark.asyncio
async def test_resource_owner_claim_is_accepted(client):
    token = mint_access_token(
        sub=f"sub-{uuid.uuid4().hex}",
        organization_id="org-from-resource-owner",
        resource_owner_only=True,
    )
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.json()["organization_id"] == "org-from-resource-owner"


@pytest.mark.asyncio
async def test_token_org_cannot_read_another_org(client):
    token_a = mint_access_token(sub="alice", organization_id="org-a", name="Alice")
    token_b = mint_access_token(sub="bob", organization_id="org-b", name="Bob")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    created = await client.post(
        "/workflows/",
        json={"name": "Alice only", "organization_id": "org-b", "initiator_id": str(uuid.uuid4())},
        headers=headers_a,
    )
    assert created.status_code == 201, created.text
    workflow_id = created.json()["id"]
    mine = await client.get("/auth/me", headers=headers_a)
    assert created.json()["initiator_id"] == mine.json()["actor_id"]

    assert (await client.get(f"/workflows/{workflow_id}", headers=headers_b)).status_code == 404
    listed = await client.get("/workflows/", params={"organization_id": "org-a"}, headers=headers_b)
    assert workflow_id not in [item["id"] for item in listed.json()["items"]]
    spoofed = await client.get(
        f"/workflows/{workflow_id}",
        params={"organization_id": "org-a"},
        headers=headers_b,
    )
    assert spoofed.status_code == 404

    vendor = await client.post(
        "/vendors",
        json={"name": "Secret Supplies", "organization_id": "org-b"},
        headers=headers_a,
    )
    assert vendor.status_code == 201, vendor.text
    assert (await client.get(f"/vendors/{vendor.json()['id']}", headers=headers_b)).status_code == 404
    assert (await client.get(f"/workflows/{workflow_id}", headers=headers_a)).status_code == 200


@pytest.mark.asyncio
async def test_password_routes_cannot_become_a_user(client, db_session):
    from sqlalchemy import func, select

    before = await db_session.scalar(select(func.count()).select_from(Actor))
    login = await client.post(
        "/auth/login",
        json={"email": "anyone@example.com", "password": "hunter2", "organization_id": "org-a"},
    )
    register = await client.post(
        "/auth/register",
        json={"name": "Anyone", "email": "anyone@example.com", "password": "hunter2"},
    )
    refresh = await client.post("/auth/refresh", json={"token": "hunter2", "sub": "alice"})
    after = await db_session.scalar(select(func.count()).select_from(Actor))
    assert login.status_code == register.status_code == refresh.status_code == 410
    assert before == after
    assert "access_token" not in login.text


def test_unset_issuer_does_not_call_the_network(monkeypatch):
    monkeypatch.setattr(settings, "zitadel_issuer", None)
    monkeypatch.setattr(settings, "zitadel_jwks_url", None)
    monkeypatch.setattr(settings, "zitadel_client_id", "sangam-test-web")
    install_test_jwks(None)

    def explode(*_args, **_kwargs):
        raise AssertionError("JWKS fetch must not run when the issuer is unset")

    monkeypatch.setattr(httpx, "get", explode)
    token = mint_access_token(sub="offline", organization_id="org-a")
    with pytest.raises(InvalidAccessToken):
        verify_access_token(token)
    install_test_jwks(None)
