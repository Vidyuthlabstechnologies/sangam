"""Create tables and seed a demo dataset.

Onboarding a prospect must not start with "run Alembic against Postgres".
This gets a working, populated backend in one command so a demo (or a
pilot evaluation) shows real data in the first meeting.

Usage:
    python -m scripts.seed_demo

Idempotent: safe to re-run. Existing rows are left alone.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import async_session_factory, engine  # noqa: E402
from app.models import (  # noqa: E402,F401  (import registers all mappers)
    Actor, ActorType, Role, Permission,
    Vendor, VendorLicence, VendorStatus, LicenceType,
)
from app.core.security import get_password_hash  # noqa: E402

DEMO_EMAIL = "qa@meridian.demo"
DEMO_PASSWORD = "sangam-demo"


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[ok] tables created")


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(Actor).where(Actor.email == DEMO_EMAIL))
        actor = existing.scalar_one_or_none()

        if actor is None:
            actor = Actor(
                id=uuid.uuid4(),
                type=ActorType.HUMAN,
                name="Priya Nair (QA Head)",
                email=DEMO_EMAIL,
                password_hash=get_password_hash(DEMO_PASSWORD),
                roles=[Role.APPROVER, Role.INITIATOR],
                permissions=[
                    Permission.CREATE_WORKFLOW,
                    Permission.READ_WORKFLOW,
                    Permission.APPROVE,
                    Permission.REJECT,
                    Permission.VERIFY,
                ],
            )
            session.add(actor)
            await session.commit()
            print(f"[ok] demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"[skip] demo user {DEMO_EMAIL} already exists")

        # A qualified vendor with a licence nearing expiry, so the expiry
        # warning path has something to show without waiting five years.
        result = await session.execute(select(Vendor).where(Vendor.name == "Kaveri Excipients"))
        if result.scalar_one_or_none() is None:
            vendor = Vendor(
                id=uuid.uuid4(),
                name="Kaveri Excipients",
                legal_name="Kaveri Excipients Private Limited",
                gstin="29AAECK9012P1ZX",
                address="Plot 7, KIADB Industrial Area, Hosur Road, Bengaluru 560099",
                contact_email="regulatory@kaveri.demo",
                contact_phone="+919845012345",
                status=VendorStatus.QUALIFIED,
            )
            session.add(vendor)
            await session.flush()

            session.add(VendorLicence(
                id=uuid.uuid4(),
                vendor_id=vendor.id,
                licence_type=LicenceType.CDSCO,
                licence_number="MFG/25/2021/KA/00219",
                issuing_authority="Drugs Control Department, Government of Karnataka",
                issue_date=date.today() - timedelta(days=1400),
                expiry_date=date.today() + timedelta(days=47),
                verified=True,
                extraction_confidence=0.94,
            ))
            await session.commit()
            print("[ok] seeded vendor 'Kaveri Excipients' (licence expires in 47 days)")
        else:
            print("[skip] vendor 'Kaveri Excipients' already exists")


async def main() -> None:
    await create_tables()
    await seed()
    await engine.dispose()
    print("\nDemo backend ready. Start it with:")
    print("  uvicorn app.main:app --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
