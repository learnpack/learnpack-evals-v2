"""Evaluation's read-side Published Language.

Reporting and Golden Dataset consume these; they never import `evaluation.domain`.
Names follow GLOSSARY.md: an `Evaluation` is the act (with its coordinates), and it carries
an `EvaluationResult` — the set of `CriterionScore`.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class CriterionScoreDTO:
    criterion_id: str
    score: int
    comment: str | None = None


@dataclass(frozen=True)
class EvaluationDTO:
    evaluation_id: UUID
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    scores: list[CriterionScoreDTO]
    attempt: int = 1
    submitted_at: datetime | None = None

    def score_for(self, criterion_id: str) -> int | None:
        for score in self.scores:
            if score.criterion_id == criterion_id:
                return score.score
        return None


@dataclass(frozen=True)
class JudgmentClaimDTO:
    claim_id: str
    status: str  # supported | refuted | insufficient
    evidence_basis: dict[str, int]  # {pass, fail, noEvidence, notApplicable, notAssessed}


@dataclass(frozen=True)
class QualityJudgmentDTO:
    """Append-only; the most recent per (content, instrument) is the current one."""

    judgment_id: UUID
    evaluation_id: UUID
    content_id: UUID
    instrument_version_id: str
    derived_at: datetime
    coverage: dict[str, Any]
    claims: list[JudgmentClaimDTO] = field(default_factory=list)


@dataclass(frozen=True)
class FindingDTO:
    finding_id: UUID
    judgment_id: UUID
    content_id: UUID
    claim_id: str
    criterion_id: str
    failure_mode: str
    quote: str | None = None  # null only on absence-derived fails (ADR-0021)
    locator: dict[str, Any] | None = None
    raised_at: datetime | None = None
