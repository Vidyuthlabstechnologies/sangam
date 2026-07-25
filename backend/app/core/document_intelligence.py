"""Turns a photographed regulatory document into typed vendor data.

Chains Sarvam's document digitisation (OCR -> markdown) with its LLM
(markdown -> structured JSON). Both primitives already existed but were
only reachable as standalone API endpoints; nothing joined them into the
vendor-onboarding flow they were bought for.

Failure policy: extraction problems produce a FAILED/NEEDS_REVIEW document
with needs_review=True. They never raise to the caller. Onboarding a
supplier must degrade to "a human checks this" rather than a 500 — a
half-created vendor is worse than a flagged one.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sarvam import SarvamAI
from app.models.document import ExtractedDocument, ExtractionStatus

logger = logging.getLogger("sangam.document_intelligence")

# Below this, a field is shown to a reviewer before it is trusted for a
# qualification decision. Chosen so the fixture licence (min 0.88 on a
# smudged address line) passes while genuinely uncertain reads do not.
CONFIDENCE_REVIEW_THRESHOLD = 0.85

POLL_INTERVAL_SECONDS = 2
MAX_POLL_ATTEMPTS = 30

EXTRACTION_PROMPT = """You are extracting structured data from an Indian pharmaceutical regulatory document.

Return ONLY valid JSON. No markdown fences, no commentary, no explanation.

Schema:
{
  "licence_number": string,
  "vendor_name": string,
  "address": string,
  "issuing_authority": string,
  "issue_date": "YYYY-MM-DD",
  "expiry_date": "YYYY-MM-DD",
  "licence_type": "CDSCO" | "STATE_FDA" | "GST" | "MCA" | "ISO" | "WHO_GMP",
  "categories": [string],
  "confidence": { "<field_name>": 0.0-1.0 }
}

Use null for any field not present in the document. Never invent a value.
Confidence reflects how clearly each value appears in the source text: a
crisply printed licence number is high, a smudged or handwritten field is
low. Downstream systems route low-confidence fields to human review, so
under-reporting confidence is far safer than over-reporting it."""


class DocumentIntelligence:
    def __init__(self, session: AsyncSession, sarvam: Optional[SarvamAI] = None):
        self.session = session
        self.sarvam = sarvam or SarvamAI()

    def _compute_review_flag(self, confidence: Dict[str, float]) -> bool:
        """Whether a human should confirm this extraction.

        Absent confidence data counts as needing review: no signal is not
        the same as a good signal.
        """
        if not confidence:
            return True
        numeric = [v for v in confidence.values() if isinstance(v, (int, float))]
        if not numeric:
            return True
        return min(numeric) < CONFIDENCE_REVIEW_THRESHOLD

    async def extract(
        self,
        file_bytes: bytes,
        filename: str,
        document_type: str = "licence",
        vendor_id: Optional[UUID] = None,
        language_code: str = "en-IN",
    ) -> ExtractedDocument:
        """Run a document through digitisation and structuring.

        Always returns a persisted ExtractedDocument, including on failure,
        so the caller has something to show a reviewer and to retry from.
        """
        doc = ExtractedDocument(
            id=uuid.uuid4(),
            vendor_id=vendor_id,
            filename=filename,
            document_type=document_type,
            status=ExtractionStatus.PROCESSING,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)

        try:
            job = await self.sarvam.vision_extract(
                document_data=file_bytes,
                filename=filename,
                language_code=language_code,
            )
            doc.sarvam_job_id = job.job_id

            markdown = await self._poll_for_output(job.job_id)
            if not markdown.strip():
                raise ValueError("Digitisation returned no text")
            doc.raw_markdown = markdown

            structured = await self._structure(markdown)
            doc.structured_data = structured

            confidence = structured.get("confidence") or {}
            numeric = [v for v in confidence.values() if isinstance(v, (int, float))]
            doc.min_confidence = min(numeric) if numeric else None
            doc.needs_review = self._compute_review_flag(confidence)
            doc.status = (
                ExtractionStatus.NEEDS_REVIEW if doc.needs_review
                else ExtractionStatus.COMPLETED
            )
        except Exception as exc:
            logger.exception("Document extraction failed for %s", filename)
            doc.status = ExtractionStatus.FAILED
            doc.needs_review = True
            doc.error_message = str(exc)

        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def _poll_for_output(self, job_id: str) -> str:
        """Wait for an async digitisation job, bounded by MAX_POLL_ATTEMPTS."""
        for _ in range(MAX_POLL_ATTEMPTS):
            status = await self.sarvam.vision_job_status(job_id)
            state = (status.get("status") or "").lower()

            if state in ("completed", "succeeded", "done"):
                return status.get("output") or status.get("output_text") or ""
            if state in ("failed", "error"):
                raise RuntimeError(f"Sarvam digitisation job {job_id} failed")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        raise TimeoutError(
            f"Sarvam job {job_id} did not complete within "
            f"{MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s"
        )

    async def _structure(self, markdown: str) -> Dict[str, Any]:
        result = await self.sarvam.llm_complete(
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": markdown},
            ],
            temperature=0.1,
        )
        return self._parse_json(result.content)

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        """Parse LLM output as JSON, tolerating markdown fences.

        Models wrap JSON in ```json fences despite instructions not to, so
        strip them rather than failing an otherwise-good extraction.
        """
        text = (content or "").strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned non-JSON output: {exc}") from exc
