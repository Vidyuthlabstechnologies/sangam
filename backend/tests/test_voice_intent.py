"""Voice commands carry financial and regulatory consequence.

The property under test is restraint: the parser must refuse far more
readily than it acts. A wrongly-approved vendor releases money and lets a
batch ship; a wrongly-refused command costs someone ten seconds.
"""
import pytest

from app.core.sarvam import SarvamLLMResult, SarvamSTTResult
from app.core.voice_intent import (
    MIN_INTENT_CONFIDENCE,
    MIN_TRANSCRIPT_CONFIDENCE,
    VoiceIntent,
    VoiceIntentParser,
    build_confirmation,
)


def _stt(transcript: str, prob: float = 0.94, lang: str = "hi-IN"):
    async def _fake(*args, **kwargs):
        return SarvamSTTResult(
            transcript=transcript, language_code=lang, language_probability=prob
        )
    return _fake


def _llm(payload: str):
    async def _fake(*args, **kwargs):
        return SarvamLLMResult(content=payload, model="sarvam-30b")
    return _fake


@pytest.fixture
def parser():
    return VoiceIntentParser()


class TestRecognisedCommands:
    @pytest.mark.asyncio
    async def test_hindi_approval(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text",
                            _stt("मैं इस विक्रेता को मंजूरी देता हूं"))
        monkeypatch.setattr(parser.sarvam, "llm_complete", _llm(
            '{"intent":"approve","subject":"Meridian Life Sciences",'
            '"reason":null,"confidence":0.93}'
        ))

        d = await parser.interpret(b"audio", language_code="hi-IN")

        assert d.intent == VoiceIntent.APPROVE
        assert d.is_actionable is True
        assert d.requires_confirmation is True
        assert "Meridian" in d.confirmation_prompt
        assert d.language_code == "hi-IN"

    @pytest.mark.asyncio
    async def test_rejection_with_reason(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text",
                            _stt("इसे अस्वीकार करें, लाइसेंस समाप्त हो गया"))
        monkeypatch.setattr(parser.sarvam, "llm_complete", _llm(
            '{"intent":"reject","subject":"batch 4471",'
            '"reason":"licence expired","confidence":0.91}'
        ))

        d = await parser.interpret(b"audio", language_code="hi-IN")

        assert d.intent == VoiceIntent.REJECT
        assert d.reason == "licence expired"
        assert d.is_actionable is True


class TestRefusesToGuess:
    @pytest.mark.asyncio
    async def test_silence_is_not_approval(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text", _stt("", prob=0.0))
        d = await parser.interpret(b"")
        assert d.intent == VoiceIntent.UNKNOWN
        assert d.is_actionable is False
        assert "No speech" in d.rejected_because

    @pytest.mark.asyncio
    async def test_noisy_transcript_refused(self, parser, monkeypatch):
        """Plant machinery makes low-confidence transcripts routine."""
        monkeypatch.setattr(parser.sarvam, "speech_to_text",
                            _stt("मंजूरी", prob=MIN_TRANSCRIPT_CONFIDENCE - 0.05))
        monkeypatch.setattr(parser.sarvam, "llm_complete", _llm(
            '{"intent":"approve","subject":"x","confidence":0.99}'
        ))

        d = await parser.interpret(b"audio")

        assert d.is_actionable is False
        assert "repeat" in d.rejected_because

    @pytest.mark.asyncio
    async def test_low_intent_confidence_downgraded_to_unknown(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text", _stt("shall we maybe approve"))
        monkeypatch.setattr(parser.sarvam, "llm_complete", _llm(
            f'{{"intent":"approve","subject":"x","confidence":{MIN_INTENT_CONFIDENCE - 0.1}}}'
        ))

        d = await parser.interpret(b"audio")

        assert d.intent == VoiceIntent.UNKNOWN
        assert d.is_actionable is False

    @pytest.mark.asyncio
    async def test_ambient_chatter_is_unknown(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text", _stt("chai ready hai kya"))
        monkeypatch.setattr(parser.sarvam, "llm_complete", _llm(
            '{"intent":"unknown","subject":null,"confidence":0.2}'
        ))

        d = await parser.interpret(b"audio")

        assert d.intent == VoiceIntent.UNKNOWN
        assert d.is_actionable is False

    @pytest.mark.asyncio
    async def test_classifier_failure_does_not_approve(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text", _stt("approve this vendor"))

        async def boom(*args, **kwargs):
            raise RuntimeError("Sarvam unavailable")

        monkeypatch.setattr(parser.sarvam, "llm_complete", boom)

        d = await parser.interpret(b"audio")

        assert d.intent == VoiceIntent.UNKNOWN
        assert d.is_actionable is False
        assert "Sarvam unavailable" in d.rejected_because

    @pytest.mark.asyncio
    async def test_garbage_model_output_does_not_approve(self, parser, monkeypatch):
        monkeypatch.setattr(parser.sarvam, "speech_to_text", _stt("approve"))
        monkeypatch.setattr(parser.sarvam, "llm_complete", _llm("sure thing boss!"))

        d = await parser.interpret(b"audio")

        assert d.is_actionable is False


class TestConfirmationPhrasing:
    def test_hindi_readback(self):
        text = build_confirmation(VoiceIntent.APPROVE, "Meridian", "hi-IN")
        assert "Meridian" in text
        assert "मंजूरी" in text

    def test_english_readback(self):
        text = build_confirmation(VoiceIntent.APPROVE, "Meridian", "en-IN")
        assert text == "Confirm approving Meridian?"

    def test_unsupported_language_falls_back_to_english(self):
        text = build_confirmation(VoiceIntent.REJECT, "Batch 9", "fr-FR")
        assert "Batch 9" in text

    def test_status_intent_has_no_confirmation(self):
        assert build_confirmation(VoiceIntent.STATUS, "x", "en-IN") == ""
