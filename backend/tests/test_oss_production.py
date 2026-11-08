"""Open-source production defaults: shared limits, object storage, mail, readiness."""
import pytest
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.billing_service import BillingService
from app.core.email_service import EmailService
from app.core.health import collect_readiness
from app.core.object_store import ObjectStore, tenant_object_key
from app.core.rate_limit import RateLimiter
from app.core.sarvam import SarvamAI, SarvamLLMResult
from app.db.session import engine_kwargs
from app.models.sangamitra_release import WalletLedgerEntryModel


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    async def incr(self, key: str) -> int:
        if self.fail:
            raise ConnectionError("redis down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int):
        self.ttls[key] = seconds
        return True


@pytest.mark.asyncio
async def test_redis_limiter_shares_a_window_and_sets_expiry():
    redis = FakeRedis()
    limiter = RateLimiter(redis=redis)
    assert await limiter.allow("10.0.0.1:/health", 2, 60) is True
    assert await limiter.allow("10.0.0.1:/health", 2, 60) is True
    assert await limiter.allow("10.0.0.1:/health", 2, 60) is False
    assert sum(redis.counts.values()) == 3
    assert all(ttl == 61 for ttl in redis.ttls.values())


@pytest.mark.asyncio
async def test_redis_limiter_fails_open_when_the_client_errors():
    limiter = RateLimiter(redis=FakeRedis(fail=True))
    assert await limiter.allow("10.0.0.1:/workflows", 1, 60) is True


@pytest.mark.asyncio
async def test_memory_limiter_when_redis_is_absent():
    limiter = RateLimiter()
    assert await limiter.allow("k", 1, 60) is True
    assert await limiter.allow("k", 1, 60) is False


def test_postgres_pool_uses_env_defaults():
    kwargs = engine_kwargs(
        "postgresql+asyncpg://user:secret@db/sangam",
        debug=False,
        pool_size=7,
        max_overflow=3,
        pool_timeout=15,
        pool_recycle=900,
        connect_timeout=4,
        command_timeout=20,
    )
    assert kwargs["pool_size"] == 7
    assert kwargs["max_overflow"] == 3
    assert kwargs["pool_timeout"] == 15
    assert kwargs["pool_recycle"] == 900
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["connect_args"] == {"timeout": 4, "command_timeout": 20}


def test_sqlite_does_not_take_a_postgres_pool():
    kwargs = engine_kwargs(
        "sqlite+aiosqlite:///./test.db",
        debug=False,
        pool_size=7,
        max_overflow=3,
        pool_timeout=15,
        pool_recycle=900,
        connect_timeout=4,
        command_timeout=20,
    )
    assert kwargs["poolclass"] is NullPool


@pytest.mark.asyncio
async def test_readiness_checks_the_database_and_skips_redis(monkeypatch):
    async def ok():
        return None

    monkeypatch.setattr("app.core.health.database_ready", ok)
    code, body = await collect_readiness()
    assert code == 200
    assert body == {"status": "ok", "checks": {"database": "ok"}}


@pytest.mark.asyncio
async def test_readiness_does_not_leak_the_database_url(monkeypatch):
    async def bad():
        raise RuntimeError("password=sangam host=db.internal user=sangam")

    monkeypatch.setattr("app.core.health.database_ready", bad)
    code, body = await collect_readiness()
    assert code == 503
    assert body["checks"]["database"] == "unavailable"
    rendered = str(body)
    assert "sangam" not in rendered
    assert "password" not in rendered


@pytest.mark.asyncio
async def test_readiness_checks_redis_only_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "redis://redis:6379/0")

    async def ok():
        return None

    seen = {"redis": 0}

    async def redis_ok():
        seen["redis"] += 1

    monkeypatch.setattr("app.core.health.database_ready", ok)
    monkeypatch.setattr("app.core.health.redis_ready", redis_ok)
    code, body = await collect_readiness()
    assert code == 200
    assert seen["redis"] == 1
    assert body["checks"]["redis"] == "ok"


def test_object_keys_are_prefixed_with_the_tenant_owner():
    key = tenant_object_key("actor-1", "doc-9", "licence.pdf")
    assert key == "tenants/actor-1/doc-9/licence.pdf"
    hostile = tenant_object_key("../other-tenant", "..\\..\\etc\\passwd")
    assert hostile.startswith("tenants/")
    assert ".." not in hostile
    assert "/" not in hostile.split("/", 1)[1].split("/", 1)[0]


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, bucket, key, data, length, content_type="application/octet-stream"):
        assert bucket == "docs"
        assert length == len(data.getvalue()) if hasattr(data, "getvalue") else True
        payload = data.read()
        assert len(payload) == length
        self.objects[key] = payload


@pytest.mark.asyncio
async def test_minio_put_uses_the_tenant_prefix_with_a_fake_client():
    fake = FakeS3()
    store = ObjectStore(client=fake, bucket="docs")
    key = await store.put_bytes(
        owner="owner-9",
        filename="a.pdf",
        data=b"hello",
        document_id="doc1",
    )
    assert key == "tenants/owner-9/doc1/a.pdf"
    assert fake.objects[key] == b"hello"


@pytest.mark.asyncio
async def test_object_store_is_a_noop_when_unset():
    store = ObjectStore(endpoint="", bucket="", access_key="", secret_key="")
    assert store.enabled is False
    assert await store.put_bytes(owner="owner", filename="a.pdf", data=b"x") is None


@pytest.mark.asyncio
async def test_extraction_stores_bytes_when_a_store_is_configured(db_session):
    from app.core.document_intelligence import DocumentIntelligence

    fake = FakeS3()
    store = ObjectStore(client=fake, bucket="docs")
    doc = await DocumentIntelligence(db_session, store=store).extract(
        file_bytes=b"%PDF",
        filename="licence.pdf",
        owner_id="owner-42",
    )
    assert doc.storage_key is not None
    assert doc.storage_key.startswith("tenants/owner-42/")
    assert fake.objects[doc.storage_key] == b"%PDF"


@pytest.mark.asyncio
async def test_smtp_is_the_mail_path(monkeypatch):
    captured = {}

    def fake_deliver(message):
        captured["to"] = message["To"]
        captured["subject"] = message["Subject"]

    monkeypatch.setattr(settings, "smtp_host", "smtp.example")
    monkeypatch.setattr("app.core.email_service.deliver_smtp", fake_deliver)
    assert await EmailService().send("person@example.com", "Hello", "<p>hi</p>", "hi") is True
    assert captured == {"to": "person@example.com", "subject": "Hello"}


@pytest.mark.asyncio
async def test_mail_is_skipped_without_smtp(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    assert await EmailService().send("person@example.com", "Hello", "<p>hi</p>") is False


@pytest.mark.asyncio
async def test_local_llm_stays_off_unless_configured(monkeypatch):
    monkeypatch.setattr(settings, "use_fixtures", False)
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)

    async def explode(*_args, **_kwargs):
        raise AssertionError("local model must stay off")

    ai = SarvamAI(api_key="")
    monkeypatch.setattr(ai, "_llm_openai_compatible", explode)
    result = await ai.llm_complete([{"role": "user", "content": "hi"}])
    assert result.content


@pytest.mark.asyncio
async def test_local_llm_is_used_when_the_base_url_is_set(monkeypatch):
    monkeypatch.setattr(settings, "use_fixtures", False)
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)

    async def fake(messages, model, temperature, max_tokens):
        assert messages[0]["content"] == "hi"
        return SarvamLLMResult(content="local-ok", model="local")

    ai = SarvamAI(api_key="")
    monkeypatch.setattr(ai, "_llm_openai_compatible", fake)
    result = await ai.llm_complete([{"role": "user", "content": "hi"}])
    assert result.content == "local-ok"
    assert result.model == "local"


@pytest.mark.asyncio
async def test_call_webhook_debit_is_idempotent_on_sqlite(db_session):
    svc = BillingService(db_session)
    wallet = await svc.get_or_create_wallet("debit-tenant", business_name="Debit Co")
    wallet.call_balance_paise = 100_000
    wallet.deployment_status = "ACTIVE"
    await db_session.commit()

    skipped = await svc.meter_call("debit-tenant", 60, None)
    assert skipped["debit_skipped"] == "call_id_required"
    assert skipped["call_balance_inr"] == 1000.0

    first = await svc.meter_call("debit-tenant", 60, "retry-me")
    await db_session.commit()
    balance = first["call_balance_inr"]
    assert balance < 1000.0

    second = await svc.meter_call("debit-tenant", 60, "retry-me")
    await db_session.commit()
    assert second["idempotent_replay"] is True
    assert second["call_balance_inr"] == balance

    call_id = "c" * 64
    await svc.meter_call("debit-tenant", 60, call_id)
    await db_session.commit()
    replay = await svc.meter_call("debit-tenant", 60, call_id)
    await db_session.commit()
    assert replay["idempotent_replay"] is True
    rows = (
        await db_session.execute(
            select(WalletLedgerEntryModel).where(WalletLedgerEntryModel.tenant_id == "debit-tenant")
        )
    ).scalars().all()
    assert rows
    assert all(len(row.transaction_id) <= 64 for row in rows)


@pytest.mark.asyncio
async def test_ledger_unique_key_drops_a_raced_second_debit(db_session):
    svc = BillingService(db_session)
    wallet = await svc.get_or_create_wallet("debit-race", business_name="Race Co")
    wallet.call_balance_paise = 100_000
    wallet.deployment_status = "ACTIVE"
    await db_session.commit()
    first = await svc.meter_call("debit-race", 60, "race-call")
    await db_session.commit()
    balance = first["call_balance_inr"]

    real = svc._ledger_entry
    state = {"n": 0}

    async def miss_once(txn_id):
        state["n"] += 1
        if state["n"] == 1:
            return None
        return await real(txn_id)

    svc._ledger_entry = miss_once
    second = await svc.meter_call("debit-race", 60, "race-call")
    await db_session.commit()
    assert second["idempotent_replay"] is True
    assert second["call_balance_inr"] == balance


@pytest.mark.asyncio
async def test_metrics_do_not_include_raw_paths(client):
    assert (await client.get("/health")).status_code == 200
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    assert "sangam_http_requests_total" in body
    assert 'path="/health"' in body
    assert "9876543210" not in body
