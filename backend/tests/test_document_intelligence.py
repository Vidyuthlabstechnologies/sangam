"""The extraction pipeline is the '14-21 days to 2 hours' claim.

Its most important property is not accuracy — it is that failure degrades
to human review rather than crashing onboarding. A vendor half-created
because Sarvam timed out is worse than one flagged for a human.
"""
import pytest

from app.core.document_intelligence import (
    DocumentIntelligence,
    CONFIDENCE_REVIEW_THRESHOLD,
)
from app.models.document import ExtractionStatus


@pytest.mark.asyncio
async def test_extracts_structured_licence(db_session):
    di = DocumentIntelligence(db_session)
    doc = await di.extract(
        file_bytes=b"%PDF-1.4 fake licence",
        filename="cdsco_licence.pdf",
        document_type="licence",
    )

    assert doc.status in (ExtractionStatus.COMPLETED, ExtractionStatus.NEEDS_REVIEW)
    assert doc.structured_data is not None
    assert doc.structured_data["licence_number"] == "MFG/25/2024/KA/00847"
    assert doc.structured_data["vendor_name"] == "Meridian Life Sciences Private Limited"
    assert doc.structured_data["expiry_date"] == "2029-03-13"
    assert doc.raw_markdown and "FORM 25" in doc.raw_markdown
    assert doc.sarvam_job_id


@pytest.mark.asyncio
async def test_records_min_confidence(db_session):
    doc = await DocumentIntelligence(db_session).extract(
        file_bytes=b"x", filename="licence.pdf",
    )
    assert doc.min_confidence == pytest.approx(0.88)


class TestReviewFlagging:
    def test_flags_when_any_field_below_threshold(self, db_session):
        di = DocumentIntelligence(db_session)
        assert di._compute_review_flag({"a": 0.99, "b": CONFIDENCE_REVIEW_THRESHOLD - 0.01}) is True

    def test_clears_when_all_fields_confident(self, db_session):
        di = DocumentIntelligence(db_session)
        assert di._compute_review_flag({"a": 0.99, "b": 0.98}) is False

    def test_no_confidence_data_means_review(self, db_session):
        """Absent confidence is not the same as high confidence."""
        di = DocumentIntelligence(db_session)
        assert di._compute_review_flag({}) is True


class TestFailureDegradation:
    @pytest.mark.asyncio
    async def test_upstream_failure_becomes_review_task_not_crash(self, db_session, monkeypatch):
        di = DocumentIntelligence(db_session)

        async def boom(*args, **kwargs):
            raise RuntimeError("Sarvam unavailable")

        monkeypatch.setattr(di.sarvam, "vision_extract", boom)

        doc = await di.extract(file_bytes=b"x", filename="licence.pdf")

        assert doc.status == ExtractionStatus.FAILED
        assert doc.needs_review is True
        assert "Sarvam unavailable" in (doc.error_message or "")

    @pytest.mark.asyncio
    async def test_non_json_llm_output_degrades(self, db_session, monkeypatch):
        from app.core.sarvam import SarvamLLMResult

        di = DocumentIntelligence(db_session)

        async def chatty(*args, **kwargs):
            return SarvamLLMResult(content="Sure! Here is the data you asked for.", model="m")

        monkeypatch.setattr(di.sarvam, "llm_complete", chatty)

        doc = await di.extract(file_bytes=b"x", filename="licence.pdf")
        assert doc.status == ExtractionStatus.FAILED
        assert doc.needs_review is True


class TestJsonParsing:
    def test_strips_markdown_fences(self):
        parsed = DocumentIntelligence._parse_json('```json\n{"a": 1}\n```')
        assert parsed == {"a": 1}

    def test_plain_json(self):
        assert DocumentIntelligence._parse_json('{"a": 1}') == {"a": 1}

    def test_bare_fence(self):
        assert DocumentIntelligence._parse_json('```\n{"a": 2}\n```') == {"a": 2}
