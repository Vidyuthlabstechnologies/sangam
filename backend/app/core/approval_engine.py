from __future__ import annotations
import logging
import uuid
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.approval import Approval, ApprovalStatus, ApprovalStrategy
from app.models.actor import Actor
from app.models.workflow import Workflow
from app.core.audit import AuditService
from app.core.safe_eval import safe_evaluate
from app.models.audit_log import AuditLog


logger = logging.getLogger("sangam.approvals")

_TEMPLATE_VAR = re.compile(r"\{\{(\w+)\}\}")


class ConditionEvaluator:
    """Evaluate an approval condition through the AST allowlist in safe_eval.

    This used to run the condition text through Python's dynamic-evaluation
    builtin with empty builtins, which is not a sandbox: the class-introspection
    chain reaches arbitrary imports. `{{name}}` template variables are now
    treated as plain name lookups against the context instead of being pasted
    into the source, so a hostile VALUE cannot change the expression either.

    A rejected or malformed condition RAISES (UnsafeExpressionError is a
    ValueError); it is not silently turned into False. Callers decide how to
    fail, and `ApprovalEngine._condition_is_unmet` fails closed.
    """

    def __init__(self, workflow_context: Dict[str, Any]):
        self.context = workflow_context

    def evaluate(self, condition: str) -> bool:
        if not condition:
            return True
        return bool(safe_evaluate(_TEMPLATE_VAR.sub(r"\1", condition), self.context))


class ApprovalEngine:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_approval(
        self,
        workflow_id: UUID,
        required_actors: List[UUID],
        strategy: ApprovalStrategy = ApprovalStrategy.ALL,
        required_count: Optional[int] = None,
        condition: Optional[str] = None,
        expires_in_minutes: Optional[int] = None,
        workflow_context: Optional[Dict[str, Any]] = None,
    ) -> Approval:
        approval = Approval(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            strategy=strategy,
            required_count=required_count,
            required_actors=[str(a) for a in required_actors],
            status=ApprovalStatus.PENDING,
            condition=condition,
            expires_at=(
                datetime.utcnow() + timedelta(minutes=expires_in_minutes)
                if expires_in_minutes else None
            ),
        )
        self.session.add(approval)
        await self.session.commit()
        await self.session.refresh(approval)

        if condition and workflow_context:
            if self._condition_is_unmet(condition, workflow_context):
                approval.status = ApprovalStatus.APPROVED
                approval.reason = "Condition auto-satisfied"
                await self.session.commit()
                await self.session.refresh(approval)

        return approval

    async def approve(
        self,
        approval_id: UUID,
        actor_id: UUID,
        reason: Optional[str] = None,
    ) -> Approval:
        result = await self.session.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")

        self._validate_action(approval, actor_id)

        # Assign a new list: approved_by is a plain JSON column, so an
        # in-place append is invisible to SQLAlchemy and never saved.
        approval.approved_by = [*approval.approved_by, str(actor_id)]
        if reason:
            approval.reason = reason

        await self._check_completion(approval)
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def reject(
        self,
        approval_id: UUID,
        actor_id: UUID,
        reason: Optional[str] = None,
    ) -> Approval:
        result = await self.session.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")

        self._validate_action(approval, actor_id)

        approval.rejected_by = [*approval.rejected_by, str(actor_id)]
        approval.reason = reason
        approval.status = ApprovalStatus.REJECTED
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def escalate(
        self,
        approval_id: UUID,
        escalated_to: UUID,
        reason: Optional[str] = None,
        *,
        acting_actor_id: UUID,
    ) -> Approval:
        """Escalate a pending approval. Only a current required approver may.

        `acting_actor_id` is the authenticated caller, never a request-body
        field: trusting a body-supplied identity is what let any user rewrite
        another approver's slot.
        """
        result = await self.session.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")

        if str(acting_actor_id) not in approval.required_actors:
            raise PermissionError("Only a required approver can escalate this approval")
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is {approval.status.value}")

        approval.escalated_to = escalated_to
        approval.status = ApprovalStatus.ESCALATED
        if reason:
            approval.reason = reason

        if str(escalated_to) not in approval.required_actors:
            approval.required_actors = approval.required_actors + [str(escalated_to)]

        await self.session.commit()
        await self.session.refresh(approval)

        await AuditService(self.session).log(
            action="approval_escalated",
            resource_type="approval",
            resource_id=str(approval.id),
            actor_id=acting_actor_id,
            workflow_id=approval.workflow_id,
            details={"escalated_to": str(escalated_to), "reason": reason},
        )
        return approval

    async def delegate(
        self,
        approval_id: UUID,
        from_actor: UUID,
        to_actor: UUID,
        *,
        acting_actor_id: UUID,
    ) -> Approval:
        """Hand one approver's slot to someone else.

        Only the approver can hand off their own slot (`acting_actor_id` is
        the authenticated caller, never taken from the request body), only
        while the approval is pending, and never to or from someone who has
        already decided, which would let a vote be moved after it was cast.
        """
        if acting_actor_id != from_actor:
            raise PermissionError("You can only delegate your own approval slot")

        result = await self.session.execute(
            select(Approval).where(Approval.id == approval_id)
        )
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError("Approval not found")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is {approval.status.value}")

        from_str, to_str = str(from_actor), str(to_actor)
        if from_str not in approval.required_actors:
            raise ValueError("Actor is not a required approver")
        if from_str == to_str:
            raise ValueError("Cannot delegate an approval to yourself")
        if from_str in approval.approved_by or from_str in approval.rejected_by:
            raise ValueError("Actor already decided this approval")
        if to_str in approval.approved_by or to_str in approval.rejected_by:
            raise ValueError("Delegate target already decided this approval")

        required = [a for a in approval.required_actors if a != from_str]
        if to_str not in required:
            required.append(to_str)
        approval.required_actors = required

        await self.session.commit()
        await self.session.refresh(approval)

        await AuditService(self.session).log(
            action="approval_delegated",
            resource_type="approval",
            resource_id=str(approval.id),
            actor_id=acting_actor_id,
            workflow_id=approval.workflow_id,
            details={"from_actor": from_str, "to_actor": to_str},
        )
        return approval

    async def check_expired(self) -> List[Approval]:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(Approval).where(
                Approval.status == ApprovalStatus.PENDING,
                Approval.expires_at.isnot(None),
                Approval.expires_at < now,
            )
        )
        expired = list(result.scalars().all())
        for approval in expired:
            approval.status = ApprovalStatus.EXPIRED
        await self.session.commit()
        return expired

    @staticmethod
    def _condition_is_unmet(condition: str, context: Dict[str, Any]) -> bool:
        """True only when the condition evaluated cleanly to false.

        A rejected or malformed condition is NOT "unmet". Treating an error as
        false auto-approved exactly the approvals whose conditions were broken
        or hostile; those now stay pending for a human.
        """
        try:
            return not ConditionEvaluator(context).evaluate(condition)
        except Exception:
            logger.warning("Approval condition rejected; leaving it pending: %r", condition)
            return False

    def _validate_action(self, approval: Approval, actor_id: UUID):
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is {approval.status}")

        actor_str = str(actor_id)
        if actor_str in approval.approved_by:
            raise ValueError("Actor already approved")

        if actor_str in approval.rejected_by:
            raise ValueError("Actor already rejected")

        if actor_str not in approval.required_actors:
            raise ValueError("Actor is not a required approver")

    async def _check_completion(self, approval: Approval):
        if approval.strategy == ApprovalStrategy.ANY:
            if len(approval.approved_by) >= 1:
                approval.status = ApprovalStatus.APPROVED

        elif approval.strategy == ApprovalStrategy.ALL:
            required_set = set(str(a) for a in approval.required_actors)
            approved_set = set(str(a) for a in approval.approved_by)
            if required_set == approved_set:
                approval.status = ApprovalStatus.APPROVED

        elif approval.strategy == ApprovalStrategy.THRESHOLD:
            threshold = approval.required_count or (len(approval.required_actors) // 2 + 1)
            if len(approval.approved_by) >= threshold:
                approval.status = ApprovalStatus.APPROVED
