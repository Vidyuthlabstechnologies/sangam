from sqlalchemy import create_engine

from app.config import settings
from app.db.base import Base
from app.models.workflow import Workflow, WaitingEvent
from app.models.actor import Actor
from app.models.approval import Approval
from app.models.handoff import Handoff
from app.models.exception import ExceptionWorkflow


async def run_migrations():
    engine = create_engine(settings.database_url.replace("+asyncpg", ""))
    Base.metadata.create_all(engine)
    engine.dispose()
