from __future__ import annotations
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.core.sarvam import SarvamAI


@dataclass
class SemanticBoundaryResult:
    boundaries: List[Dict[str, Any]] = field(default_factory=list)
    risk_score: float = 0.0
    summary: str = ""


BOUNDARY_TYPES = [
    "data_privacy",
    "regulatory_compliance",
    "security_classification",
    "financial_approval",
    "legal_review",
    "cross_domain_transfer",
    "vendor_externalization",
    "intellectual_property",
    "ethical_review",
    "audit_requirement",
]


BOUNDARY_SYSTEM_PROMPT = """You are a semantic boundary detection AI for enterprise workflow orchestration.

Analyze the given workflow and identify semantic boundaries — points where data, control, or responsibility crosses trust domains, regulatory environments, security classifications, or organizational units.

Return ONLY valid JSON — no markdown, no explanation. If no boundaries exist, return [].

Each boundary object:
{
  "type": "data_privacy" | "regulatory_compliance" | "security_classification" | "financial_approval" | "legal_review" | "cross_domain_transfer" | "vendor_externalization" | "intellectual_property" | "ethical_review" | "audit_requirement",
  "description": "brief explanation",
  "severity": "low" | "medium" | "high" | "critical",
  "suggested_action": "what should happen (approval, encryption, review, notification, etc.)"
}"""


class SemanticBoundaryDetector:
    def __init__(self, sarvam: Optional[SarvamAI] = None):
        self.sarvam = sarvam or SarvamAI()

    async def detect(
        self,
        workflow_name: str,
        workflow_description: str,
        actor_types: List[str],
        phases: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SemanticBoundaryResult:
        prompt = self._build_prompt(
            workflow_name, workflow_description, actor_types, phases, metadata
        )

        result = await self.sarvam.llm_complete(
            messages=[
                {"role": "system", "content": BOUNDARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model="sarvam-30b",
            temperature=0.2,
        )

        boundaries = self._parse_boundaries(result.content)
        risk_score = self._calculate_risk_score(boundaries)
        summary = self._generate_summary(boundaries, risk_score)

        return SemanticBoundaryResult(
            boundaries=boundaries,
            risk_score=risk_score,
            summary=summary,
        )

    def _build_prompt(
        self,
        name: str,
        description: str,
        actor_types: List[str],
        phases: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        return f"""Workflow Name: {name}
Description: {description}
Actor Types: {', '.join(actor_types)}
Phases: {', '.join(phases)}
Additional Context: {metadata or 'None'}

Identify all semantic boundaries in this workflow."""

    def _parse_boundaries(self, content: str) -> List[Dict[str, Any]]:
        import json
        import re

        json_match = re.search(r'\[.*?\]', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        boundaries = []
        for line in content.split("\n"):
            line = line.strip()
            for btype in BOUNDARY_TYPES:
                if btype in line.lower():
                    boundaries.append({
                        "type": btype,
                        "description": line,
                        "severity": "medium",
                        "suggested_action": "review",
                    })
                    break

        return boundaries

    def _calculate_risk_score(self, boundaries: List[Dict]) -> float:
        severity_weights = {
            "low": 0.25,
            "medium": 0.5,
            "high": 0.75,
            "critical": 1.0,
        }

        if not boundaries:
            return 0.0

        total_weight = sum(
            severity_weights.get(b.get("severity", "medium"), 0.5)
            for b in boundaries
        )
        return min(total_weight / len(boundaries), 1.0)

    def _generate_summary(self, boundaries: List[Dict], risk_score: float) -> str:
        if not boundaries:
            return "No semantic boundaries detected."

        critical_count = sum(1 for b in boundaries if b.get("severity") == "critical")
        high_count = sum(1 for b in boundaries if b.get("severity") == "high")

        parts = [f"Detected {len(boundaries)} semantic boundaries."]
        if critical_count:
            parts.append(f"{critical_count} critical.")
        if high_count:
            parts.append(f"{high_count} high severity.")

        risk_level = "Low" if risk_score < 0.3 else "Medium" if risk_score < 0.6 else "High"
        parts.append(f"Overall risk: {risk_level} ({risk_score:.1%}).")

        return " ".join(parts)
