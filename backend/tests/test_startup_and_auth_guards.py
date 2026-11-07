"""Production must not boot forgeable, and a bad token must be a 401, not a 500."""
import uuid

import pytest

from app.config import Settings, validate_production_settings
from app.core.security import create_access_token


def _settings(**overrides):
    return Settings(_env_file=None, **overrides)


def test_development_may_use_the_default_secret():
    validate_production_settings(_settings(environment="development"))


def test_production_refuses_the_default_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_production_settings(_settings(environment="production"))


def test_production_refuses_a_short_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_production_settings(_settings(environment="production", jwt_secret="short"))


def test_production_refuses_fixture_mode():
    with pytest.raises(RuntimeError, match="USE_FIXTURES"):
        validate_production_settings(
            _settings(environment="production", jwt_secret="x" * 40, use_fixtures=True)
        )


def test_production_accepts_a_strong_secret():
    validate_production_settings(_settings(environment="production", jwt_secret="x" * 40))


@pytest.mark.asyncio
async def test_token_with_a_malformed_subject_is_401_not_500(client):
    token = create_access_token("not-a-uuid")

    resp = await client.get(
        f"/payments/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )

    assert resp.status_code == 401
