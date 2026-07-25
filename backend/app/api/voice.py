"""Voice-driven approvals.

Deliberately two calls, not one:

    POST /voice/interpret   -> what did the operator ask for?
    POST /voice/commit      -> do it

A single call that transcribed and immediately approved would let one
misheard word release money. The interpret step returns a read-back phrase
(and audio for it, via TTS) so the operator hears the action restated before
anything is committed.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.core.approval_engine import ApprovalEngine
from app.core.audit import AuditService
from app.core.sarvam import SarvamAI
from app.core.voice_intent import VoiceIntent, VoiceIntentParser
from app.db.session import get_session
from app.models.actor import Actor
from app.models.approval import Approval

router = APIRouter(prefix="/voice", tags=["voice"])

logger = logging.getLogger("sangam.voice")

MAX_AUDIO_BYTES = 10 * 1024 * 1024


class VoiceInterpretOut(BaseModel):
    intent: str
    transcript: str
    language_code: str
    transcript_confidence: float
    intent_confidence: float
    subject: Optional[str] = None
    reason: Optional[str] = None
    actionable: bool
    requires_confirmation: bool
    confirmation_prompt: str = ""
    confirmation_audio_base64: Optional[str] = None
    rejected_because: Optional[str] = None


class VoiceCommitRequest(BaseModel):
    approval_id: UUID
    intent: str
    transcript: str
    language_code: str = "en-IN"
    reason: Optional[str] = None


class VoiceCommitOut(BaseModel):
    approval_id: UUID
    status: str
    spoken_confirmation: str
    confirmation_audio_base64: Optional[str] = None


@router.post("/interpret", response_model=VoiceInterpretOut)
async def interpret_voice_command(
    file: UploadFile = File(...),
    language_code: str = Form("unknown"),
    subject_hint: Optional[str] = Form(None),
    speak_confirmation: bool = Form(True),
    current_actor: Actor = Depends(get_current_actor),
):
    """Transcribe and classify a spoken instruction. Commits nothing."""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty audio upload")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio exceeds {MAX_AUDIO_BYTES // (1024 * 1024)}MB limit",
        )

    parser = VoiceIntentParser()
    decision = await parser.interpret(
        audio_bytes=audio,
        filename=file.filename or "command.wav",
        language_code=language_code,
        subject_hint=subject_hint,
    )

    audio_b64: Optional[str] = None
    if speak_confirmation and decision.is_actionable and decision.confirmation_prompt:
        # Read the action back in the operator's own language, so a
        # mishearing is caught by the person, not by an auditor later.
        try:
            tts = await SarvamAI().text_to_speech(
                text=decision.confirmation_prompt,
                target_language_code=_tts_language(decision.language_code),
            )
            audio_b64 = tts.audio_base64
        except Exception:
            logger.exception("Confirmation TTS failed; returning text only")

    return VoiceInterpretOut(
        intent=decision.intent.value,
        transcript=decision.transcript,
        language_code=decision.language_code,
        transcript_confidence=decision.transcript_confidence,
        intent_confidence=decision.intent_confidence,
        subject=decision.subject,
        reason=decision.reason,
        actionable=decision.is_actionable,
        requires_confirmation=decision.requires_confirmation,
        confirmation_prompt=decision.confirmation_prompt,
        confirmation_audio_base64=audio_b64,
        rejected_because=decision.rejected_because,
    )


@router.post("/commit", response_model=VoiceCommitOut)
async def commit_voice_decision(
    req: VoiceCommitRequest,
    session: AsyncSession = Depends(get_session),
    current_actor: Actor = Depends(get_current_actor),
):
    """Apply a confirmed voice decision to an approval.

    Runs through the same ApprovalEngine as the web and mobile clients, so
    a voice approval is indistinguishable downstream — same state machine,
    same audit trail. The transcript is recorded alongside, because "what
    did they actually say" is what an auditor will ask.
    """
    try:
        intent = VoiceIntent(req.intent.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown intent: {req.intent}")

    if intent not in (VoiceIntent.APPROVE, VoiceIntent.REJECT):
        raise HTTPException(
            status_code=400,
            detail=f"Intent '{intent.value}' cannot be committed against an approval",
        )

    result = await session.execute(select(Approval).where(Approval.id == req.approval_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    engine = ApprovalEngine(session)
    voice_reason = f"[voice:{req.language_code}] {req.transcript}"
    if req.reason:
        voice_reason = f"{voice_reason} — {req.reason}"

    try:
        if intent == VoiceIntent.APPROVE:
            approval = await engine.approve(req.approval_id, current_actor.id, voice_reason)
            spoken = "स्वीकृत" if req.language_code.startswith("hi") else "Approved"
        else:
            approval = await engine.reject(req.approval_id, current_actor.id, voice_reason)
            spoken = "अस्वीकृत" if req.language_code.startswith("hi") else "Rejected"
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await AuditService(session).log(
        action="voice_decision_committed",
        resource_type="approval",
        resource_id=str(req.approval_id),
        actor_id=current_actor.id,
        workflow_id=approval.workflow_id,
        details={
            "intent": intent.value,
            "transcript": req.transcript,
            "language_code": req.language_code,
            "channel": "voice",
        },
    )

    audio_b64: Optional[str] = None
    try:
        tts = await SarvamAI().text_to_speech(
            text=spoken, target_language_code=_tts_language(req.language_code)
        )
        audio_b64 = tts.audio_base64
    except Exception:
        logger.exception("Result TTS failed; returning text only")

    return VoiceCommitOut(
        approval_id=req.approval_id,
        status=approval.status.value,
        spoken_confirmation=spoken,
        confirmation_audio_base64=audio_b64,
    )


def _tts_language(language_code: str) -> str:
    """Map a detected language onto one Sarvam TTS supports."""
    from app.core.sarvam import TTS_LANGUAGES

    return language_code if language_code in TTS_LANGUAGES else "en-IN"
