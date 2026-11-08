"""Delete or anonymise personal data the authenticated actor owns.

Workflows that still have another participant are left intact: this deployment
has no organization table, so a shared workflow is not one person's private
record. The actor row itself is anonymised and deactivated rather than deleted,
because payments and workflows reference it.
"""
from __future__ import annotations

from typing import List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import other_participants
from app.models.actor import Actor
from app.models.capability import RegisteredCapability
from app.models.document import ExtractedDocument
from app.models.vendor import Vendor
from app.models.voice_callback import VoiceCallback
from app.models.workflow import Workflow


async def purge_actor_personal_data(session: AsyncSession, actor: Actor, tenant_id: str) -> List[str]:
    deleted: List[str] = []

    attrs = actor.extra_attributes or {}
    if attrs.get("fcm_tokens"):
        deleted.append("fcm_tokens")
    actor.extra_attributes = {}
    actor.password_hash = None
    actor.email = None
    actor.name = "Deleted user"
    actor.is_active = False
    actor.roles = []
    actor.permissions = []
    deleted.append("actor_credentials")

    vendors = (
        await session.execute(select(Vendor).where(Vendor.owner_actor_id == actor.id))
    ).scalars().all()
    if vendors:
        vendor_ids = [vendor.id for vendor in vendors]
        await session.execute(delete(ExtractedDocument).where(ExtractedDocument.vendor_id.in_(vendor_ids)))
        for vendor in vendors:
            await session.delete(vendor)
        deleted.append("vendors")
        deleted.append("documents")

    tenant_ids = {tenant_id, str(actor.id)}
    callbacks = (
        await session.execute(select(VoiceCallback).where(VoiceCallback.tenant_id.in_(tenant_ids)))
    ).scalars().all()
    if callbacks:
        for row in callbacks:
            await session.delete(row)
        deleted.append("voice_callbacks")

    caps = (
        await session.execute(
            select(RegisteredCapability).where(RegisteredCapability.owner_actor_id == actor.id)
        )
    ).scalars().all()
    if caps:
        for cap in caps:
            await session.delete(cap)
        deleted.append("capabilities")

    workflows = (
        await session.execute(select(Workflow).where(Workflow.initiator_id == actor.id))
    ).scalars().all()
    anonymised = False
    for workflow in workflows:
        if await other_participants(session, workflow, actor.id):
            continue
        workflow.name = "Deleted workflow"
        workflow.description = None
        workflow.extra_attributes = None
        anonymised = True
    if anonymised:
        deleted.append("owned_workflows")
    return deleted
