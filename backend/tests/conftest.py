import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_sangam.db"

# Force fixture mode for the whole suite. Without this, settings loads the
# real .env and tests would hit live Sarvam (billable) and live Razorpay
# (money movement). Tests must never depend on, or touch, external services.
settings.use_fixtures = True


@pytest.fixture(autouse=True)
def _force_fixture_mode(monkeypatch):
    """Belt-and-braces: re-assert fixture mode per test in case a test
    mutates settings and fails before restoring it.

    Optional integrations stay off so a developer .env cannot make pytest
    call Redis, MinIO, SMTP, or a local model.
    """
    monkeypatch.setattr(settings, "use_fixtures", True)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "s3_endpoint_url", None)
    monkeypatch.setattr(settings, "s3_bucket", None)
    monkeypatch.setattr(settings, "s3_access_key", None)
    monkeypatch.setattr(settings, "s3_secret_key", None)
    monkeypatch.setattr(settings, "llm_base_url", None)
    monkeypatch.setattr(settings, "smtp_host", None)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def current_actor(db_session: AsyncSession):
    """A persisted human actor used as the authenticated caller."""
    import uuid as _uuid
    from app.models.actor import Actor, ActorType, Role

    actor = Actor(
        id=_uuid.uuid4(),
        type=ActorType.HUMAN,
        name="Test QA Head",
        email="qa@example.test",
        roles=[Role.APPROVER],
        permissions=[],
    )
    db_session.add(actor)
    await db_session.commit()
    await db_session.refresh(actor)
    return actor


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, current_actor):
    """Authenticate API calls by overriding the auth dependency.

    Overriding rather than minting a real JWT keeps these tests focused on
    the endpoint under test; token issuance has its own coverage.
    """
    from app.api.dependencies import get_current_actor

    async def override_actor():
        return current_actor

    app.dependency_overrides[get_current_actor] = override_actor
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_actor, None)


@pytest_asyncio.fixture
async def sample_actors(db_session: AsyncSession):
    """Two actors, for handoff sender/receiver."""
    import uuid as _uuid
    from app.models.actor import Actor, ActorType

    actors = [
        Actor(id=_uuid.uuid4(), type=ActorType.HUMAN, name="Store Keeper", roles=[], permissions=[]),
        Actor(id=_uuid.uuid4(), type=ActorType.HUMAN, name="QA Inspector", roles=[], permissions=[]),
    ]
    db_session.add_all(actors)
    await db_session.commit()
    for a in actors:
        await db_session.refresh(a)
    return actors


@pytest_asyncio.fixture
async def sample_workflow(db_session: AsyncSession, sample_actors):
    import uuid as _uuid
    from app.models.workflow import Workflow, WorkflowPhase, WorkflowState

    wf = Workflow(
        id=_uuid.uuid4(),
        name="Vendor qualification - Meridian",
        initiator_id=sample_actors[0].id,
        current_phase=WorkflowPhase.EXECUTION,
        state=WorkflowState.ACTIVE,
        phases=[],
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf


@pytest_asyncio.fixture
async def owned_workflow(db_session: AsyncSession, current_actor):
    """A workflow initiated by the authenticated caller."""
    import uuid as _uuid
    from app.models.workflow import Workflow, WorkflowPhase, WorkflowState

    wf = Workflow(
        id=_uuid.uuid4(),
        name="Caller-owned workflow",
        initiator_id=current_actor.id,
        current_phase=WorkflowPhase.EXECUTION,
        state=WorkflowState.ACTIVE,
        phases=[],
    )
    db_session.add(wf)
    await db_session.commit()
    await db_session.refresh(wf)
    return wf
