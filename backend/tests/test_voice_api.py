"""The voice endpoints must not become a one-shot 'speak and it happens'.

Interpretation and commit are separate calls on purpose. These tests pin
that separation and the refusal behaviour, since the failure mode here is
money moving on a misheard word.
"""
import uuid

import pytest
import pytest_asyncio

from app.models.approval import Approval, ApprovalStatus, ApprovalStrategy


@pytest_asyncio.fixture
async def approval(db_session, sample_workflow, current_actor):
    """A pending approval on which the authenticated caller is the approver."""
    ap = Approval(
        id=uuid.uuid4(),
        workflow_id=sample_workflow.id,
        strategy=ApprovalStrategy.ANY,
        status=ApprovalStatus.PENDING,
        required_actors=[str(current_actor.id)],
    )
    db_session.add(ap)
    await db_session.commit()
    await db_session.refresh(ap)
    return ap


@pytest.mark.asyncio
async def test_interpret_returns_intent_without_committing(client, auth_headers, approval):
    resp = await client.post(
        "/voice/interpret",
        files={"file": ("cmd.wav", b"RIFFfake", "audio/wav")},
        data={"language_code": "hi-IN", "subject_hint": "Meridian Life Sciences"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["transcript"]
    assert body["language_code"] == "hi-IN"
    assert body["requires_confirmation"] is True

    # Interpreting must not have committed anything.
    assert approval.status == ApprovalStatus.PENDING


@pytest.mark.asyncio
async def test_empty_audio_rejected(client, auth_headers):
    resp = await client.post(
        "/voice/interpret",
        files={"file": ("cmd.wav", b"", "audio/wav")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_commit_approves_through_the_normal_engine(
    client, auth_headers, approval, db_session
):
    resp = await client.post(
        "/voice/commit",
        json={
            "approval_id": str(approval.id),
            "intent": "approve",
            "transcript": "मैं इस विक्रेता को मंजूरी देता हूं",
            "language_code": "hi-IN",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] in ("approved", "pending")
    assert body["spoken_confirmation"] == "स्वीकृत"

    await db_session.refresh(approval)
    assert approval.status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
async def test_commit_rejects_unknown_intent(client, auth_headers, approval):
    resp = await client.post(
        "/voice/commit",
        json={
            "approval_id": str(approval.id),
            "intent": "unknown",
            "transcript": "chai ready hai kya",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_commit_refuses_non_decision_intents(client, auth_headers, approval):
    """'status' is a query, not a decision — it must not touch the approval."""
    resp = await client.post(
        "/voice/commit",
        json={
            "approval_id": str(approval.id),
            "intent": "status",
            "transcript": "what is the status",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "cannot be committed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_commit_404s_for_unknown_approval(client, auth_headers):
    resp = await client.post(
        "/voice/commit",
        json={
            "approval_id": "00000000-0000-0000-0000-000000000000",
            "intent": "approve",
            "transcript": "approve",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_voice_endpoints_require_auth(client):
    resp = await client.post(
        "/voice/interpret",
        files={"file": ("cmd.wav", b"RIFFfake", "audio/wav")},
    )
    assert resp.status_code in (401, 403)
