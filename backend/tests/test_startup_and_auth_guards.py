"""Production must not boot without Zitadel, and a bad token must be a 401."""
import uuid

import pytest

from app.config import Settings, settings, validate_production_settings
from tests.identity_tokens import mint_access_token


def _settings(**overrides):
    return Settings(_env_file=None, **overrides)


def test_development_may_omit_the_issuer():
    validate_production_settings(_settings(environment="development"))


def test_production_refuses_a_missing_issuer():
    with pytest.raises(RuntimeError, match="ZITADEL_ISSUER"):
        validate_production_settings(_settings(environment="production", zitadel_client_id="web"))


def test_production_refuses_an_http_issuer():
    with pytest.raises(RuntimeError, match="ZITADEL_ISSUER"):
        validate_production_settings(
            _settings(
                environment="production",
                zitadel_issuer="http://localhost:8080",
                zitadel_client_id="web",
            )
        )


def test_production_refuses_fixture_mode():
    with pytest.raises(RuntimeError, match="USE_FIXTURES"):
        validate_production_settings(
            _settings(
                environment="production",
                zitadel_issuer="https://auth.example.test",
                zitadel_client_id="web",
                use_fixtures=True,
            )
        )


@pytest.mark.asyncio
async def test_production_refuses_to_seed_live_pilot_wallets(db_session, monkeypatch):
    from app.core.billing_service import seed_live_tenants

    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(RuntimeError, match="production"):
        await seed_live_tenants(db_session)


def test_production_accepts_an_https_issuer():
    validate_production_settings(
        _settings(
            environment="production",
            zitadel_issuer="https://auth.example.test",
            zitadel_project_id="project",
        )
    )


@pytest.mark.asyncio
async def test_zitadel_subject_need_not_be_a_uuid(client):
    """Zitadel subjects are opaque strings. A non-UUID subject must not 500."""
    token = mint_access_token(sub="not-a-uuid", organization_id="org-a")
    resp = await client.get(
        f"/payments/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404

    rejected = await client.get(
        f"/payments/{uuid.uuid4()}", headers={"Authorization": "Bearer not-a-token"}
    )
    assert rejected.status_code == 401
