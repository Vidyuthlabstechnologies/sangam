"""Validate Zitadel access tokens. Sangam does not issue them.

The resource server checks the signature against the issuer's JWKS, then
reads the subject and organization from the verified claims. Callers must
not pass an organization id in from a request body, query string, or
Android intent: those values are ignored because they are not signed.
"""
from __future__ import annotations

import json
import threading
from typing import Any, Optional, cast

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.actor import Actor, ActorType, Permission, Role

_ORG_CLAIM = "urn:zitadel:iam:org:id"
_RESOURCE_OWNER_CLAIM = "urn:zitadel:iam:user:resourceowner:id"

_lock = threading.Lock()
_cached_jwks: Optional[dict] = None
_test_jwks: Optional[dict] = None


class InvalidAccessToken(Exception):
    """The bearer token is missing, forged, expired, or not an org member."""


def install_test_jwks(jwks: Optional[dict]) -> None:
    """Point verification at a local key set. Tests use this so nothing is fetched."""
    global _test_jwks, _cached_jwks
    with _lock:
        _test_jwks = jwks
        _cached_jwks = None


def clear_jwks_cache() -> None:
    global _cached_jwks
    with _lock:
        _cached_jwks = None


def verify_access_token(token: str) -> dict[str, Any]:
    """Return verified claims, or raise InvalidAccessToken. Never calls the network
    unless an issuer or JWKS URL is configured and no test key set is installed.
    """
    if not token or token.count(".") != 2:
        raise InvalidAccessToken("Invalid or expired token")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken("Invalid or expired token") from exc
    if header.get("alg") != "RS256":
        raise InvalidAccessToken("Invalid or expired token")

    jwk = _select_key(header.get("kid"), _load_jwks())
    try:
        public_key = cast(RSAPublicKey, RSAAlgorithm.from_jwk(json.dumps(jwk)))
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=_audiences(),
            issuer=_issuer(),
            leeway=30,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken("Invalid or expired token") from exc
    if not str(claims.get("sub") or "").strip():
        raise InvalidAccessToken("Invalid or expired token")
    organization_id_from_claims(claims)
    return claims


def organization_id_from_claims(claims: dict[str, Any]) -> str:
    """Organization the token was issued for. Request parameters are not consulted."""
    for key in (_ORG_CLAIM, _RESOURCE_OWNER_CLAIM, "org_id"):
        found = _as_id(claims.get(key))
        if found:
            return found
    org = claims.get("org")
    if isinstance(org, dict):
        found = _as_id(org.get("id"))
        if found:
            return found
    found = _as_id(org)
    if found:
        return found
    raise InvalidAccessToken("Invalid or expired token")


def _as_id(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _issuer() -> str:
    issuer = (settings.zitadel_issuer or "").strip().rstrip("/")
    if not issuer:
        raise InvalidAccessToken("Invalid or expired token")
    return issuer


def _audiences() -> list[str]:
    audiences = [
        value.strip()
        for value in (
            settings.zitadel_client_id,
            settings.zitadel_android_client_id,
            settings.zitadel_project_id,
        )
        if value and value.strip()
    ]
    if not audiences:
        raise InvalidAccessToken("Invalid or expired token")
    return audiences


def _load_jwks() -> dict:
    global _cached_jwks
    with _lock:
        if _test_jwks is not None:
            return _test_jwks
        if _cached_jwks is not None:
            return _cached_jwks
        url = _jwks_url()
        if not url:
            raise InvalidAccessToken("Invalid or expired token")
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        document = response.json()
    except Exception as exc:
        raise InvalidAccessToken("Invalid or expired token") from exc
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        raise InvalidAccessToken("Invalid or expired token")
    with _lock:
        _cached_jwks = document
    return document


def _jwks_url() -> Optional[str]:
    configured = (settings.zitadel_jwks_url or "").strip()
    if configured:
        return configured
    issuer = (settings.zitadel_issuer or "").strip().rstrip("/")
    if not issuer:
        return None
    return f"{issuer}/oauth/v2/keys"


def _select_key(kid: Optional[str], document: dict) -> dict:
    keys = [key for key in document.get("keys", []) if isinstance(key, dict) and key.get("kty") == "RSA"]
    if kid:
        keys = [key for key in keys if key.get("kid") == kid]
    if not keys:
        raise InvalidAccessToken("Invalid or expired token")
    return keys[0]


async def link_actor(session: AsyncSession, claims: dict[str, Any]) -> Actor:
    """Return the local actor for this Zitadel subject, creating it on first use.

    The row is keyed by (subject, organization). A password is never stored.
    An inactive row stays inactive so account deletion cannot be walked back
    by presenting the same token.
    """
    subject = str(claims["sub"]).strip()
    organization_id = organization_id_from_claims(claims)
    actor = await _find_actor(session, subject, organization_id)
    if actor is not None:
        if not actor.is_active:
            raise InvalidAccessToken("Actor not found or inactive")
        return actor

    email = claims.get("email")
    name = claims.get("name") or claims.get("preferred_username") or email or "User"
    actor = Actor(
        type=ActorType.HUMAN,
        name=str(name)[:256],
        email=str(email)[:256] if isinstance(email, str) and email else None,
        zitadel_sub=subject,
        zitadel_org_id=organization_id,
        password_hash=None,
        roles=[Role.INITIATOR],
        permissions=[Permission.CREATE_WORKFLOW, Permission.READ_WORKFLOW],
    )
    session.add(actor)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        actor = await _find_actor(session, subject, organization_id)
        if actor is None or not actor.is_active:
            raise InvalidAccessToken("Actor not found or inactive")
        return actor
    await session.refresh(actor)
    return actor


async def _find_actor(session: AsyncSession, subject: str, organization_id: str) -> Optional[Actor]:
    result = await session.execute(
        select(Actor).where(Actor.zitadel_sub == subject, Actor.zitadel_org_id == organization_id)
    )
    return result.scalar_one_or_none()
