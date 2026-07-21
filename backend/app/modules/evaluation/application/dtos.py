"""Evaluation's read-side Published Language.

Reporting and Golden Dataset consume these; they never import `evaluation.domain`.
Names follow GLOSSARY.md: an `Evaluation` is the act (with its coordinates), and it carries
an `EvaluationResult` — the set of `CriterionScore`.
"""

from dataclasses import dataclass
from datetime import datetime
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
    rubric_version_id: str
    scores: list[CriterionScoreDTO]
    attempt: int = 1
    submitted_at: datetime | None = None

    def score_for(self, criterion_id: str) -> int | None:
        for score in self.scores:
            if score.criterion_id == criterion_id:
                return score.score
        return None
