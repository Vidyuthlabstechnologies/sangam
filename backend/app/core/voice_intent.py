"""Turn a spoken utterance into a workflow decision.

This is what makes the Sarvam integration load-bearing rather than a
transcription toy: a shop-floor operator speaks in their own language and
the words drive the same approval state machine the web and mobile clients
use, with the same audit trail.

Safety posture, in order of importance:

  1. **Never infer approval from ambiguity.** An unclear utterance returns
     UNKNOWN and the caller does nothing. Silence is safer than a wrongly
     approved vendor.
  2. **Confirmation before commit.** A recognised intent is returned with a
     read-back phrase; committing is a separate call. A misheard word must
     not release funds on its own.
  3. **Language preserved.** The transcript, detected language, and
     confidence are all retained for the audit record, because "who
     approved this and what did they actually say" is the question an
     auditor asks.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.sarvam import SarvamAI

logger = logging.getLogger("sangam.voice_intent")

# Below this, the utterance is treated as not understood. Voice in a plant
# competes with machinery noise, so a low-confidence transcript is common
# and must not be acted on.
MIN_TRANSCRIPT_CONFIDENCE = 0.60

# The model must clear this to have its intent acted on at all.
MIN_INTENT_CONFIDENCE = 0.70


class VoiceIntent(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    HOLD = "hold"
    STATUS = "status"
    UNKNOWN = "unknown"


INTENT_PROMPT = """You classify spoken shop-floor instructions in an Indian pharmaceutical plant.

The speaker may use Hindi, English, or a mix. Return ONLY valid JSON, no
commentary:

{
  "intent": "approve" | "reject" | "hold" | "status" | "unknown",
  "subject": "<what the instruction refers to, verbatim, or null>",
  "reason": "<stated reason, or null>",
  "confidence": 0.0-1.0
}

Rules:
- "unknown" whenever the instruction is unclear, incomplete, or could be
  read two ways. Do not guess.
- Approval and rejection carry financial and regulatory consequence.
  Only use them when the speaker clearly and unambiguously expresses that
  decision.
- Chatter, greetings, and background speech are "unknown".
- confidence reflects certainty about the INTENT, not transcription
  quality."""


@dataclass
class VoiceDecision:
    intent: VoiceIntent
    transcript: str
    language_code: str
    transcript_confidence: float
    intent_confidence: float
    subject: Optional[str] = None
    reason: Optional[str] = None
    requires_confirmation: bool = True
    confirmation_prompt: str = ""
    rejected_because: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """Whether this decision may be acted on after confirmation."""
        return (
            self.intent in (VoiceIntent.APPROVE, VoiceIntent.REJECT, VoiceIntent.HOLD)
            and self.rejected_because is None
        )


# Read-back phrasing per language. The operator hears the action restated
# before it happens, so a misheard command is caught by the human rather
# than by an auditor months later.
_CONFIRMATION_TEMPLATES = {
    "hi-IN": {
        VoiceIntent.APPROVE: "क्या आप {subject} को मंजूरी देना चाहते हैं?",
        VoiceIntent.REJECT: "क्या आप {subject} को अस्वीकार करना चाहते हैं?",
        VoiceIntent.HOLD: "क्या आप {subject} को रोकना चाहते हैं?",
    },
    "en-IN": {
        VoiceIntent.APPROVE: "Confirm approving {subject}?",
        VoiceIntent.REJECT: "Confirm rejecting {subject}?",
        VoiceIntent.HOLD: "Confirm placing {subject} on hold?",
    },
}


def build_confirmation(intent: VoiceIntent, subject: str, language_code: str) -> str:
    templates = _CONFIRMATION_TEMPLATES.get(
        language_code, _CONFIRMATION_TEMPLATES["en-IN"]
    )
    template = templates.get(intent)
    if not template:
        return ""
    return template.format(subject=subject or "this item")


class VoiceIntentParser:
    def __init__(self, sarvam: Optional[SarvamAI] = None):
        self.sarvam = sarvam or SarvamAI()

    async def interpret(
        self,
        audio_bytes: bytes,
        filename: str = "command.wav",
        language_code: str = "unknown",
        subject_hint: Optional[str] = None,
    ) -> VoiceDecision:
        """Transcribe an utterance and classify what it is asking for.

        Returns a decision in every case, including failure. Callers branch
        on ``is_actionable`` rather than handling exceptions.
        """
        stt = await self.sarvam.speech_to_text(
            audio_data=audio_bytes,
            filename=filename,
            language_code=language_code,
        )

        decision = VoiceDecision(
            intent=VoiceIntent.UNKNOWN,
            transcript=stt.transcript,
            language_code=stt.language_code,
            transcript_confidence=stt.language_probability,
            intent_confidence=0.0,
        )

        if not stt.transcript.strip():
            decision.rejected_because = "No speech detected"
            return decision

        if stt.language_probability < MIN_TRANSCRIPT_CONFIDENCE:
            decision.rejected_because = (
                f"Transcript confidence {stt.language_probability:.2f} below "
                f"{MIN_TRANSCRIPT_CONFIDENCE:.2f}; ask the speaker to repeat"
            )
            return decision

        try:
            parsed = await self._classify(stt.transcript, subject_hint)
        except Exception as exc:
            logger.exception("Voice intent classification failed")
            decision.rejected_because = f"Could not interpret instruction: {exc}"
            return decision

        decision.raw = parsed
        decision.subject = parsed.get("subject") or subject_hint
        decision.reason = parsed.get("reason")
        decision.intent_confidence = _as_confidence(parsed.get("confidence"))

        try:
            decision.intent = VoiceIntent(str(parsed.get("intent", "unknown")).lower())
        except ValueError:
            decision.intent = VoiceIntent.UNKNOWN

        if decision.intent == VoiceIntent.UNKNOWN:
            decision.rejected_because = "Instruction not understood"
            return decision

        if decision.intent_confidence < MIN_INTENT_CONFIDENCE:
            decision.rejected_because = (
                f"Intent confidence {decision.intent_confidence:.2f} below "
                f"{MIN_INTENT_CONFIDENCE:.2f}"
            )
            decision.intent = VoiceIntent.UNKNOWN
            return decision

        decision.confirmation_prompt = build_confirmation(
            decision.intent,
            decision.subject or subject_hint or "",
            decision.language_code,
        )
        return decision

    async def _classify(
        self, transcript: str, subject_hint: Optional[str]
    ) -> Dict[str, Any]:
        user_content = transcript
        if subject_hint:
            user_content = (
                f"Pending item: {subject_hint}\nSpoken instruction: {transcript}"
            )

        result = await self.sarvam.llm_complete(
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        return _parse_json(result.content)


def _as_confidence(value: Any) -> float:
    """Coerce a model-supplied confidence to a float in [0, 1].

    Models return this field as a number, a numeric string, or occasionally
    a per-field mapping. Anything uninterpretable becomes 0.0, which fails
    the threshold check — the safe direction.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return 0.0
    if isinstance(value, dict) and value:
        numeric = [v for v in value.values() if isinstance(v, (int, float))]
        return max(0.0, min(1.0, min(numeric))) if numeric else 0.0
    return 0.0


def _parse_json(content: str) -> Dict[str, Any]:
    """Parse model output as JSON, tolerating fences and surrounding prose."""
    if not content or not content.strip():
        raise ValueError("Model returned empty content")

    text = content.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
        text = text.strip()

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)
