"""Fixture mode must be a transport swap, not a different code path.

These tests also act as a safety net: if fixture mode ever silently stops
engaging, the suite would start making billable Sarvam calls and reaching
a live payment gateway.
"""
import base64

import pytest

from app.config import settings
from app.core.payments import RazorpayService
from app.core.sarvam import SarvamAI


class TestSarvamFixtures:
    @pytest.mark.asyncio
    async def test_stt_returns_hindi_transcript(self):
        result = await SarvamAI().speech_to_text(audio_data=b"fake", language_code="hi-IN")
        assert result.transcript == "मैं इस विक्रेता को मंजूरी देता हूं"
        assert result.language_code == "hi-IN"
        assert 0.0 <= result.language_probability <= 1.0

    @pytest.mark.asyncio
    async def test_tts_returns_decodable_wav(self):
        result = await SarvamAI().text_to_speech(text="स्वीकृत", target_language_code="hi-IN")
        audio = base64.b64decode(result.audio_base64)
        assert audio.startswith(b"RIFF")
        assert b"WAVE" in audio

    @pytest.mark.asyncio
    async def test_vision_extract_then_status_yields_licence(self):
        sarvam = SarvamAI()
        job = await sarvam.vision_extract(document_data=b"%PDF-1.4", filename="licence.pdf")
        assert job.job_id
        status = await sarvam.vision_job_status(job.job_id)
        assert status["status"] == "completed"
        assert "MFG/25/2024/KA/00847" in status["output"]

    @pytest.mark.asyncio
    async def test_llm_returns_parseable_json(self):
        import json

        result = await SarvamAI().llm_complete(messages=[{"role": "user", "content": "x"}])
        parsed = json.loads(result.content)
        assert parsed["licence_number"] == "MFG/25/2024/KA/00847"
        assert "confidence" in parsed


class TestRazorpayFixtures:
    @pytest.mark.asyncio
    async def test_create_order_never_touches_live_client(self):
        svc = RazorpayService()
        assert svc.use_fixtures is True
        assert svc.client is None, "A live Razorpay client must not exist in fixture mode"

        order = await svc.create_order(amount=2500.0, receipt="rcpt_1")
        assert order["amount"] == 250000  # rupees -> paise
        assert order["currency"] == "INR"
        assert order["status"] == "created"

    @pytest.mark.asyncio
    async def test_upi_intent_order_carries_upi_method(self):
        order = await RazorpayService().create_upi_intent_order(amount=100.0, receipt="r")
        assert order["method"]["upi"]["flow"] == "intent"


def test_fixture_mode_is_active_for_tests():
    """Guards the guard: if this fails, other tests may be hitting live APIs."""
    assert settings.use_fixtures is True
