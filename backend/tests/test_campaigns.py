"""Bulk AI calling campaigns, in fixture mode.

What these pin: CSV contacts are normalised and DND/do-not-call numbers are
never dialled; a live campaign needs consent, credit and calling hours; it keeps
exactly `concurrency` calls live and refills a line when a webhook frees one;
it stops dialling the moment the goal is met; opt-outs land on the do-not-call
list; simulations reach their target with scripted multilingual transcripts and
never touch the calling platform; and one business cannot see another's campaign.
"""
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core import campaign_engine as engine
from app.core.billing_service import BillingService
from app.core.samvaad import SamvaadClient
from app.models.campaign import CampaignContact, DoNotCallEntry
from app.models.samvaad import SamvaadAgentBinding
from app.models.sangamitra_release import utcnow_naive
from tests.identity_tokens import login

pytestmark = pytest.mark.asyncio

APP_ID = "realty-caller"


@pytest_asyncio.fixture
async def tenant(current_actor, db_session):
    tid = str(current_actor.id)
    wallet = await BillingService(db_session).get_or_create_wallet(
        tid, owner_actor_id=current_actor.id, business_name="Sri Sai Developers"
    )
    wallet.call_balance_paise = 100_000
    wallet.deployment_status = "ACTIVE"
    db_session.add(SamvaadAgentBinding(
        tenant_id=tid, app_id=APP_ID, app_version=3, label="Sales",
        connection_id="conn-exotel-001", agent_phone_number="+918047168000",
    ))
    await db_session.commit()
    return tid


class Clock:
    """Moves the engine's notion of now; calls and windows follow it."""

    def __init__(self, monkeypatch):
        # 11:00 IST on a weekday: inside calling hours.
        self.now = datetime(2026, 11, 16, 5, 30)
        monkeypatch.setattr(engine, "utcnow_naive", lambda: self.now)

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def placed(monkeypatch):
    """Every outbound call the engine asks Samvaad to place, with its webhook URL."""
    calls: list[dict] = []
    real = SamvaadClient.create_outbound_call

    async def spy(self, **kwargs):
        attempt_id = await real(self, **kwargs)
        calls.append({**kwargs, "attempt_id": attempt_id})
        return attempt_id

    monkeypatch.setattr(SamvaadClient, "create_outbound_call", spy)
    return calls


def _csv(n: int, start: int = 0) -> str:
    lines = ["name,phone,language,plot_size"]
    for i in range(start, start + n):
        lines.append(f"Customer {i},98765{i:05d},te,200 sq yd")
    return "\n".join(lines)


async def _live_campaign(client, headers, **overrides):
    body = {
        "name": "Villa plots", "mode": "live", "app_id": APP_ID, "goal": "Site visit booked",
        "target_count": 2, "language": "Telugu", "concurrency": 3, "consent_confirmed": True,
        "success_variable": "visit_booked", "success_values": ["yes"], **overrides,
    }
    r = await client.post("/campaigns", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _webhook(client, call, *, status="connected", duration=60.0, final=None):
    path = httpx.URL(call["webhook_url"]).path
    return await client.post(path, json={
        "attempt_id": call["attempt_id"], "status": status, "duration": duration,
        "interaction_id": "20261116/x", "final_agent_variables": final,
        "interaction_transcript": [
            {"role": "agent", "en_text": "Would you like to visit the site?"},
            {"role": "user", "en_text": "Yes, Saturday."},
        ],
    })


# ------------------------------------------------------------------ parsing


def test_csv_normalises_indian_numbers_and_keeps_extra_columns():
    text = (
        "Name,Mobile,Lang,DND,Plot Size\n"
        "Ravi,98765 43210,te,,200\n"
        "Asha,+91-91234-56789,hindi,no,\n"
        "Old,09123456780,,yes,\n"
        "Bad,12345,,,\n"
        "Intl,+14155550100,en,,\n"
    )
    good, bad = engine.parse_contacts_csv(text)
    assert [g["phone"] for g in good] == ["+919876543210", "+919123456789", "+919123456780", "+14155550100"]
    assert good[0]["language"] == "Telugu" and good[1]["language"] == "Hindi"
    assert good[0]["variables"] == {"plot_size": "200"}
    assert [g["dnd"] for g in good] == [False, False, True, False]
    assert bad == [{"line": 5, "reason": "phone number not recognised"}]


def test_csv_without_phone_column_is_rejected():
    with pytest.raises(Exception) as exc:
        engine.parse_contacts_csv("name,email\nA,a@b.c\n")
    assert "phone" in str(exc.value.detail)


async def test_upload_dedupes_and_suppresses_dnd(client, auth_headers, tenant, db_session):
    db_session.add(DoNotCallEntry(tenant_id=tenant, phone="+919876500001", reason="opted_out"))
    await db_session.commit()
    c = await _live_campaign(client, auth_headers)
    text = _csv(3) + "\nDup,9876500000,te,\nDnd,9000000001,te,\n"
    r = await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": text}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # 3 + Dnd row added; 1 duplicate; 1 on the do-not-call list.
    assert body["duplicates"] == 1
    assert body["suppressed"] == 1
    assert body["added"] == 3
    assert body["campaign"]["counts"] == {"pending": 3, "suppressed": 1}


# ------------------------------------------------------------------ live


async def test_live_campaign_needs_an_outbound_agent(client, auth_headers, tenant):
    r = await client.post("/campaigns", json={
        "name": "x", "mode": "live", "app_id": "not-mine", "goal": "g", "target_count": 1,
    }, headers=auth_headers)
    assert r.status_code == 404


async def test_calling_hours_must_stay_inside_trai_window(client, auth_headers, tenant):
    r = await client.post("/campaigns", json={
        "name": "x", "mode": "live", "app_id": APP_ID, "goal": "g", "target_count": 1,
        "window_start_hour": 8,
    }, headers=auth_headers)
    assert r.status_code == 422


async def test_live_start_requires_consent(client, auth_headers, tenant):
    c = await _live_campaign(client, auth_headers, consent_confirmed=False)
    await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": _csv(2)}, headers=auth_headers)
    r = await client.post(f"/campaigns/{c['id']}/start", json={}, headers=auth_headers)
    assert r.status_code == 409
    assert "DND" in r.json()["detail"]


async def test_live_campaign_waits_outside_calling_hours(client, auth_headers, tenant, monkeypatch, placed):
    clock = Clock(monkeypatch)
    clock.now = datetime(2026, 11, 16, 16, 0)  # 21:30 IST
    c = await _live_campaign(client, auth_headers)
    await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": _csv(4)}, headers=auth_headers)
    r = await client.post(f"/campaigns/{c['id']}/start", json={}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    assert "calling hours" in r.json()["hold_reason"]
    assert placed == []


async def test_live_campaign_dials_in_parallel_refills_and_stops_at_target(
    client, auth_headers, tenant, monkeypatch, placed, db_session
):
    Clock(monkeypatch)
    c = await _live_campaign(client, auth_headers)  # target 2 bookings, 3 lines
    await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": _csv(8)}, headers=auth_headers)
    r = await client.post(f"/campaigns/{c['id']}/start", json={}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["counts"] == {"dialing": 3, "pending": 5}
    assert len(placed) == 3
    first = placed[0]
    assert first["agent_variables"]["plot_size"] == "200 sq yd"
    assert first["overrides"]["initial_language_name"] == "Telugu"
    assert first["user_phone_number"] == "+919876500000"

    # One booking: its line is refilled with the next contact.
    r = await _webhook(client, placed[0], final={"visit_booked": "Yes", "summary": "Booked Sat 11am"})
    assert r.status_code == 200, r.text
    assert len(placed) == 4
    # No answer: not a success, line refilled.
    await _webhook(client, placed[1], status="no_answer", duration=0)
    assert len(placed) == 5

    live = (await client.get(f"/campaigns/{c['id']}/live", headers=auth_headers)).json()
    assert live["campaign"]["success_count"] == 1
    assert live["progress"] == 0.5
    assert live["simulated"] is False
    assert len(live["active"]) == 3
    assert live["recent"][0]["summary"] in ("Did not pick up.", "Booked Sat 11am")
    assert all("*" in a["phone"] for a in live["active"])  # never the full number

    # Second booking meets the goal: queue is skipped, nobody else is dialled.
    await _webhook(client, placed[2], final={"visit_booked": "yes"})
    live = (await client.get(f"/campaigns/{c['id']}/live", headers=auth_headers)).json()
    assert live["campaign"]["status"] == "target_reached"
    assert live["campaign"]["counts"]["skipped"] == 3
    assert len(placed) == 5
    # Webhook retries do not double count.
    await _webhook(client, placed[2], final={"visit_booked": "yes"})
    live = (await client.get(f"/campaigns/{c['id']}/live", headers=auth_headers)).json()
    assert live["campaign"]["success_count"] == 2

    detail = (await client.get(
        f"/campaigns/{c['id']}/contacts/{live['recent'][0]['id']}", headers=auth_headers
    )).json()
    assert detail["transcript"][1]["content"] == "Yes, Saturday."


async def test_opt_out_lands_on_do_not_call_list(client, auth_headers, tenant, monkeypatch, placed, db_session):
    Clock(monkeypatch)
    c = await _live_campaign(client, auth_headers, concurrency=1)
    await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": _csv(2)}, headers=auth_headers)
    await client.post(f"/campaigns/{c['id']}/start", json={}, headers=auth_headers)
    await _webhook(client, placed[0], final={"opt_out": "true"})
    dnc = (await db_session.execute(select(DoNotCallEntry.phone).where(DoNotCallEntry.tenant_id == tenant))).scalars().all()
    assert "+919876500000" in dnc

    # A later campaign never dials them.
    c2 = await _live_campaign(client, auth_headers)
    r = await client.post(f"/campaigns/{c2['id']}/contacts", json={"csv": _csv(1)}, headers=auth_headers)
    assert r.json()["suppressed"] == 1


async def test_live_campaign_holds_when_credit_runs_out(client, auth_headers, tenant, monkeypatch, placed, db_session):
    Clock(monkeypatch)
    c = await _live_campaign(client, auth_headers, concurrency=1)
    await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": _csv(3)}, headers=auth_headers)
    await client.post(f"/campaigns/{c['id']}/start", json={}, headers=auth_headers)
    wallet = await BillingService(db_session).get_wallet(tenant)
    wallet.call_balance_paise = 0
    await db_session.commit()
    await _webhook(client, placed[0], status="busy", duration=0)
    live = (await client.get(f"/campaigns/{c['id']}/live", headers=auth_headers)).json()
    assert "credit" in live["campaign"]["hold_reason"]
    assert len(placed) == 1


async def test_pause_stops_new_calls(client, auth_headers, tenant, monkeypatch, placed):
    Clock(monkeypatch)
    c = await _live_campaign(client, auth_headers, concurrency=1)
    await client.post(f"/campaigns/{c['id']}/contacts", json={"csv": _csv(3)}, headers=auth_headers)
    await client.post(f"/campaigns/{c['id']}/start", json={}, headers=auth_headers)
    assert (await client.post(f"/campaigns/{c['id']}/pause", headers=auth_headers)).json()["status"] == "paused"
    await _webhook(client, placed[0], status="no_answer", duration=0)
    assert len(placed) == 1
    r = await client.post(f"/campaigns/{c['id']}/resume", headers=auth_headers)
    assert r.json()["status"] == "running"
    assert len(placed) == 2


# ------------------------------------------------------------------ simulation


async def test_demo_simulation_reaches_target_without_dialling(client, auth_headers, tenant, monkeypatch, placed):
    clock = Clock(monkeypatch)
    r = await client.post("/campaigns/demo", json={"contacts": 200, "target_count": 20, "concurrency": 80},
                          headers=auth_headers)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["mode"] == "simulation"
    assert c["counts"] == {"dialing": 80, "pending": 120}

    # Mid-call: the board shows live conversation lines in the contact's language.
    clock.advance(30)
    live = (await client.get(f"/campaigns/{c['id']}/live", headers=auth_headers)).json()
    assert live["simulated"] is True
    lines = [a["line"]["content"] for a in live["active"] if a["line"]]
    assert lines, live["active"][:3]
    assert any(any("\u0c00" <= ch <= "\u0c7f" for ch in t) for t in lines)  # Telugu script

    for _ in range(40):
        clock.advance(20)
        live = (await client.get(f"/campaigns/{c['id']}/live", headers=auth_headers)).json()
        if live["campaign"]["status"] != "running":
            break
    assert live["campaign"]["status"] == "target_reached"
    assert live["campaign"]["success_count"] >= 20
    assert live["progress"] == 1.0
    vs = live["versus_telecaller"]
    assert vs["one_telecaller_seconds"] > vs["ai_elapsed_seconds"]
    assert vs["telecallers_to_match"] >= 2
    assert placed == []  # nothing reached the calling platform

    booked = (await client.get(f"/campaigns/{c['id']}/contacts?succeeded=true&limit=5", headers=auth_headers)).json()
    detail = (await client.get(f"/campaigns/{c['id']}/contacts/{booked[0]['id']}", headers=auth_headers)).json()
    assert detail["summary"].startswith("Interested")
    assert len(detail["transcript"]) >= 6
    assert detail["transcript"][0]["role"] == "agent"


async def test_simulation_is_deterministic_per_contact(tenant, db_session):
    from app.models.campaign import CallCampaign

    campaign = CallCampaign(tenant_id=tenant, created_by=tenant, name="s", mode="simulation", goal="g",
                            target_count=1, language="Hindi", success_values=["true"])
    contact = CampaignContact(name="Rahul Sharma", phone="+919000000001", language="Hindi")
    import uuid
    contact.id = uuid.uuid4()
    contact.attempts = 1
    now = utcnow_naive()
    assert engine.plan_simulated_call(campaign, contact, now) == engine.plan_simulated_call(campaign, contact, now)


# ------------------------------------------------------------------ isolation


async def test_other_business_cannot_see_campaign(client, auth_headers, tenant):
    c = (await client.post("/campaigns/demo", json={"contacts": 10, "start": False}, headers=auth_headers)).json()
    from app.api.dependencies import get_current_actor
    from app.main import app

    app.dependency_overrides.pop(get_current_actor, None)
    token, _ = await login(client, name="Stranger")
    h = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"/campaigns/{c['id']}/live", headers=h)).status_code == 404
    assert (await client.post(f"/campaigns/{c['id']}/start", headers=h)).status_code == 404
    assert (await client.get("/campaigns", headers=h)).json() == []
