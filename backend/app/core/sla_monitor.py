from __future__ import annotations
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.sla import SLAConfig, SLATracking
from app.models.workflow import Workflow, WorkflowState


class SLAMonitor:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_config(
        self,
        name: str,
        target_minutes: int,
        description: Optional[str] = None,
        warning_minutes: Optional[int] = None,
        escalation_minutes: Optional[int] = None,
        escalation_actor_id: Optional[UUID] = None,
    ) -> SLAConfig:
        config = SLAConfig(
            id=uuid.uuid4(),
            name=name,
            description=description,
            target_minutes=target_minutes,
            warning_minutes=warning_minutes,
            escalation_minutes=escalation_minutes,
            escalation_actor_id=escalation_actor_id,
        )
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def start_tracking(
        self,
        workflow_id: UUID,
        sla_config_id: UUID,
    ) -> SLATracking:
        result = await self.session.execute(
            select(SLAConfig).where(SLAConfig.id == sla_config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            raise ValueError("SLA config not found")

        now = datetime.utcnow()
        tracking = SLATracking(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            sla_config_id=sla_config_id,
            started_at=now,
            deadline_at=now + timedelta(minutes=config.target_minutes),
            warning_at=(
                now + timedelta(minutes=config.warning_minutes)
                if config.warning_minutes else None
            ),
            escalation_at=(
                now + timedelta(minutes=config.escalation_minutes)
                if config.escalation_minutes else None
            ),
            status="active",
        )
        self.session.add(tracking)
        await self.session.commit()
        await self.session.refresh(tracking)
        return tracking

    async def complete_tracking(self, tracking_id: UUID) -> SLATracking:
        result = await self.session.execute(
            select(SLATracking).where(SLATracking.id == tracking_id)
        )
        tracking = result.scalar_one_or_none()
        if not tracking:
            raise ValueError("SLA tracking not found")
        tracking.completed_at = datetime.utcnow()
        tracking.status = "completed"
        await self.session.commit()
        await self.session.refresh(tracking)
        return tracking

    async def check_overdue(self) -> List[SLATracking]:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(SLATracking).where(
                SLATracking.status == "active",
                SLATracking.deadline_at < now,
            )
        )
        overdue = list(result.scalars().all())
        for tracking in overdue:
            tracking.status = "breached"
            tracking.breached_at = now
        await self.session.commit()
        return overdue

    async def check_warnings(self) -> List[SLATracking]:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(SLATracking).where(
                SLATracking.status == "active",
                SLATracking.warning_at.isnot(None),
                SLATracking.warning_at < now,
                SLATracking.deadline_at > now,
            )
        )
        return list(result.scalars().all())

    async def check_escalations(self) -> List[SLATracking]:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(SLATracking).where(
                and_(
                    SLATracking.status == "active",
                    SLATracking.escalation_at.isnot(None),
                    SLATracking.escalation_at < now,
                    SLATracking.deadline_at > now,
                )
            )
        )
        return list(result.scalars().all())
