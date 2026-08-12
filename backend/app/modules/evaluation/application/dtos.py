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
class RatificationDTO:
    """One ADR-0019 act: this assessor may evaluate with that instrument version.

    The act has an author, and the console shows it: a ratification is a decision somebody
    made, not a state the system reached.
    """

    assessor_id: UUID
    instrument_version_id: str
    ratified_at: datetime
    ratified_by: UUID


@dataclass(frozen=True)
class CriterionOutcomeDTO:
    """One criterion's outcome under a published judgment, in its own right.

    `judgment_claims.evidence_basis` already counts these five states, but only per claim
    and pre-aggregated — a consumer that must attribute a criterion to something other than
    its claim (ADR-0023: to a quality, deduplicated) needs the criterion's identity, which a
    count has lost. `derived` marks the absence-derived `fail` (ADR-0021).
    """

    judgment_id: UUID
    content_id: UUID
    criterion_id: str
    outcome: str  # pass | fail | not_applicable | no_evidence | not_assessed
    derived: bool


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
