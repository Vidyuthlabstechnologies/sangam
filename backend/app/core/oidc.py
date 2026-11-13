"""Validate bearer tokens from the identity providers Sangam trusts. Sangam does not issue them.

Two issuers are accepted, each only when configured:

* Firebase Authentication (``FIREBASE_PROJECT_ID``). The Android app signs users
  in with Google or email/password through Firebase and sends the Firebase ID
  token. Google signs it with rotating RS256 keys published as a JWKS.
* Self-hosted Zitadel (``ZITADEL_ISSUER``), kept for the web dashboard.

The resource server checks the signature against the issuer's JWKS, then
reads the subject and organization from the verified claims. Callers must
not pass an organization id in from a request body, query string, or
Android intent: those values are ignored because they are not signed.

Keys are cached in-process, so a request costs no network round trip. A token
signed with an unknown ``kid`` triggers at most one refetch per minute, which
picks up Google's key rotation without letting forged tokens hammer the JWKS.
"""
from __future__ import annotations

import json
import threading
import time
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
_ORG_CLAIM_KEYS = (_ORG_CLAIM, _RESOURCE_OWNER_CLAIM, "org_id", "org")

FIREBASE_ISSUER_PREFIX = "https://securetoken.google.com/"
FIREBASE_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
)
# Each Firebase user gets a personal workspace. The id is derived from the
# verified uid on the server, so a client cannot choose someone else's.
FIREBASE_ORG_PREFIX = "fb-"

_JWKS_TTL_SECONDS = 3600
_JWKS_MIN_REFRESH_SECONDS = 60

_lock = threading.Lock()
# url -> (document, fetched_at)
_jwks_cache: dict[str, tuple[dict, float]] = {}
_test_jwks: Optional[dict] = None


class InvalidAccessToken(Exception):
    """The bearer token is missing, forged, expired, or not an org member."""


def install_test_jwks(jwks: Optional[dict]) -> None:
    """Point verification at a local key set. Tests use this so nothing is fetched."""
    global _test_jwks
    with _lock:
        _test_jwks = jwks
        _jwks_cache.clear()


def clear_jwks_cache() -> None:
    with _lock:
        _jwks_cache.clear()


def verify_access_token(token: str) -> dict[str, Any]:
    """Return verified claims, or raise InvalidAccessToken. Never calls the network
    unless an issuer is configured and no test key set is installed.
    """
    if not token or token.count(".") != 2:
        raise InvalidAccessToken("Invalid or expired token")
    try:
        header = jwt.get_unverified_header(token)
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken("Invalid or expired token") from exc
    if header.get("alg") != "RS256":
        raise InvalidAccessToken("Invalid or expired token")

    firebase_issuer = _firebase_issuer()
    if firebase_issuer and unverified.get("iss") == firebase_issuer:
        return _verify_firebase(token, header, firebase_issuer)
    return _verify_zitadel(token, header)


def _verify_zitadel(token: str, header: dict) -> dict[str, Any]:
    claims = _decode(
        token,
        header,
        jwks_url=_zitadel_jwks_url(),
        audience=_audiences(),
        issuer=_issuer(),
    )
    organization_id_from_claims(claims)
    return claims


def _verify_firebase(token: str, header: dict, issuer: str) -> dict[str, Any]:
    project_id = issuer[len(FIREBASE_ISSUER_PREFIX):]
    claims = _decode(
        token,
        header,
        jwks_url=(settings.firebase_jwks_url or "").strip() or FIREBASE_JWKS_URL,
        audience=[project_id],
        issuer=issuer,
        require=["exp", "iat", "sub", "iss", "aud", "auth_time"],
    )
    now = time.time()
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, (int, float)) or auth_time > now + 30:
        raise InvalidAccessToken("Invalid or expired token")
    firebase = claims.get("firebase")
    provider = firebase.get("sign_in_provider") if isinstance(firebase, dict) else None
    if provider in (None, "anonymous", "custom"):
        # Anonymous sessions have no person behind them, and Sangam mints no custom tokens.
        raise InvalidAccessToken("Invalid or expired token")
    if provider == "password" and settings.firebase_require_verified_email and not claims.get("email_verified"):
        raise InvalidAccessToken("Email address is not verified")

    subject = str(claims["sub"]).strip()
    if len(subject) > 128:
        raise InvalidAccessToken("Invalid or expired token")
    # Never let token claims pick the workspace. Drop any org-shaped claim and
    # pin the organization to this uid.
    sanitized = {key: value for key, value in claims.items() if key not in _ORG_CLAIM_KEYS}
    sanitized["org_id"] = FIREBASE_ORG_PREFIX + subject
    if not claims.get("email_verified"):
        # Keep only addresses Google asserted or the user verified.
        sanitized.pop("email", None)
    return sanitized


def _decode(
    token: str,
    header: dict,
    *,
    jwks_url: Optional[str],
    audience: list[str],
    issuer: str,
    require: Optional[list[str]] = None,
) -> dict[str, Any]:
    jwk = _select_key(header.get("kid"), jwks_url)
    try:
        public_key = cast(RSAPublicKey, RSAAlgorithm.from_jwk(json.dumps(jwk)))
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            leeway=30,
            options={"require": require or ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken("Invalid or expired token") from exc
    if not str(claims.get("sub") or "").strip():
        raise InvalidAccessToken("Invalid or expired token")
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


def _firebase_issuer() -> Optional[str]:
    project_id = (settings.firebase_project_id or "").strip()
    return FIREBASE_ISSUER_PREFIX + project_id if project_id else None


def _load_jwks(url: Optional[str], *, force: bool = False) -> dict:
    with _lock:
        if _test_jwks is not None:
            return _test_jwks
        if not url:
            raise InvalidAccessToken("Invalid or expired token")
        cached = _jwks_cache.get(url)
        now = time.monotonic()
        if cached is not None:
            document, fetched_at = cached
            age = now - fetched_at
            if age < _JWKS_TTL_SECONDS and not (force and age >= _JWKS_MIN_REFRESH_SECONDS):
                return document
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        document = response.json()
    except Exception as exc:
        if cached is not None:
            # Keep serving the last good key set if the JWKS endpoint blips.
            return cached[0]
        raise InvalidAccessToken("Invalid or expired token") from exc
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        if cached is not None:
            return cached[0]
        raise InvalidAccessToken("Invalid or expired token")
    with _lock:
        _jwks_cache[url] = (document, time.monotonic())
    return document


def _zitadel_jwks_url() -> Optional[str]:
    configured = (settings.zitadel_jwks_url or "").strip()
    if configured:
        return configured
    issuer = (settings.zitadel_issuer or "").strip().rstrip("/")
    if not issuer:
        return None
    return f"{issuer}/oauth/v2/keys"


def _matching_keys(kid: Optional[str], document: dict) -> list[dict]:
    keys = [key for key in document.get("keys", []) if isinstance(key, dict) and key.get("kty") == "RSA"]
    if kid:
        keys = [key for key in keys if key.get("kid") == kid]
    return keys


def _select_key(kid: Optional[str], jwks_url: Optional[str]) -> dict:
    keys = _matching_keys(kid, _load_jwks(jwks_url))
    if not keys and kid:
        # The issuer may have rotated keys since the last fetch.
        keys = _matching_keys(kid, _load_jwks(jwks_url, force=True))
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
