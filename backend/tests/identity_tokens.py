"""Local RS256 tokens for tests. The suite never contacts a Zitadel server."""
from __future__ import annotations

import json
import time
import uuid
from typing import Optional

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.core.oidc import install_test_jwks

TEST_ISSUER = "https://zitadel.test/local"
TEST_CLIENT_ID = "sangam-test-web"
_KID = "test-key"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_jwk = json.loads(RSAAlgorithm.to_jwk(_private_key.public_key()))
_public_jwk.update({"kid": _KID, "use": "sig", "alg": "RS256"})
TEST_JWKS = {"keys": [_public_jwk]}


def install() -> None:
    install_test_jwks(TEST_JWKS)


def mint_access_token(
    *,
    sub: str,
    organization_id: Optional[str] = "org-test",
    name: str = "Test User",
    email: Optional[str] = None,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
    include_org: bool = True,
    resource_owner_only: bool = False,
    algorithm: str = "RS256",
    key=None,
    expires_in: int = 3600,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": issuer or TEST_ISSUER,
        "aud": audience or TEST_CLIENT_ID,
        "exp": now + expires_in,
        "iat": now,
        "name": name,
        "email": email or f"{sub}@example.test",
    }
    if include_org and organization_id is not None:
        claim = (
            "urn:zitadel:iam:user:resourceowner:id"
            if resource_owner_only
            else "urn:zitadel:iam:org:id"
        )
        payload[claim] = organization_id
    return jwt.encode(
        payload,
        _private_key if key is None else key,
        algorithm=algorithm,
        headers={"kid": _KID},
    )


async def login(client, name: str = "User", organization_id: Optional[str] = None, subject: Optional[str] = None):
    """JIT a local actor with a test access token and return (token, actor_id)."""
    organization_id = organization_id or f"org-{uuid.uuid4().hex}"
    subject = subject or f"sub-{uuid.uuid4().hex}"
    token = mint_access_token(sub=subject, organization_id=organization_id, name=name)
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    return token, response.json()["actor_id"]
