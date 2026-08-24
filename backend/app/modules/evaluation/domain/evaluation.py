"""`Evaluation` aggregate — the core act. Pure Python.

An `Evaluation` is a concrete **act**, not a unique fact: a given `Assessor` evaluating a
given content version with a given rubric. Identity is its own `evaluationId`; there is
deliberately **no** uniqueness on `(assessor, content, instrumentVersion)`, so repetitions coexist
— an `LLMJudge` run N times to measure dispersion is a first-class case (ADR-0005).

Human anti-duplication lives in the `Assignment` (Orchestration), not here.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

SCORE_MIN = 1
SCORE_MAX = 5


class InvalidEvaluation(Exception):
    """The evaluation breaks an invariant of its aggregate."""


@dataclass(frozen=True)
class CriterionScore:
    """A judgement on one criterion. Distinct from a `ComputedMetric` (a raw measurement).

    Four states, out of two fields (ADR-0052 §4, ADR-0053 §3):

    | `score` | `derived` | |
    |---|---|---|
    | 1-5   | false | a judgement |
    | null  | false | the assessor abstained -- they looked and could not judge it |
    | null  | true  | the item does not apply to this content's format |
    | 1     | true  | the course could have declared the datum and did not |

    `derived` is ADR-0021's own column ported here, for the reason it was added there: it
    distinguishes in data "someone judged it" from "the mechanics derived it". Nothing that
    reports what humans said may average a derived row, and the bottom of the scale is an
    answer -- never an abstention wearing a number.
    """

    criterion_id: str
    score: int | None
    comment: str | None = None
    derived: bool = False

    def __post_init__(self) -> None:
        if not self.criterion_id or not self.criterion_id.strip():
            raise InvalidEvaluation("criterion_id is required")
        if self.score is None:
            return
        # bool is an int subclass — reject it explicitly.
        if isinstance(self.score, bool) or not isinstance(self.score, int):
            raise InvalidEvaluation(f"score for '{self.criterion_id}' must be an integer")
        if not SCORE_MIN <= self.score <= SCORE_MAX:
            raise InvalidEvaluation(
                f"score for '{self.criterion_id}' must be between "
                f"{SCORE_MIN} and {SCORE_MAX}, got {self.score}"
            )


@dataclass(frozen=True)
class EvaluationResult:
    """The set of `CriterionScore` of one evaluation."""

    scores: list[CriterionScore]

    def covers_exactly(self, criterion_ids: list[str]) -> bool:
        return {s.criterion_id for s in self.scores} == set(criterion_ids)

    def score_for(self, criterion_id: str) -> int | None:
        for score in self.scores:
            if score.criterion_id == criterion_id:
                return score.score
        return None


@dataclass
class Evaluation:
    """Aggregate root. Immutable once submitted (MVP has no draft state)."""

    id: UUID
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    result: EvaluationResult
    attempt: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None

    @classmethod
    def submit(
        cls,
        evaluation_id: UUID,
        assessor_id: UUID,
        content_id: UUID,
        instrument_version_id: str,
        scores: list[CriterionScore],
        rubric_criterion_ids: list[str],
        attempt: int = 1,
    ) -> "Evaluation":
        """Build a submitted evaluation, enforcing every invariant.

        `rubric_criterion_ids` arrives as plain data, so this aggregate never depends on the
        Rubric Authoring module (ARCHITECTURE.md §3).
        """
        if not rubric_criterion_ids:
            raise InvalidEvaluation("the rubric version has no criteria")

        duplicates = {s.criterion_id for s in scores if _count(scores, s.criterion_id) > 1}
        if duplicates:
            raise InvalidEvaluation(f"duplicated criterion scores: {sorted(duplicates)}")

        result = EvaluationResult(scores=list(scores))
        if not result.covers_exactly(rubric_criterion_ids):
            missing = sorted(set(rubric_criterion_ids) - {s.criterion_id for s in scores})
            extra = sorted({s.criterion_id for s in scores} - set(rubric_criterion_ids))
            details = []
            if missing:
                details.append(f"missing {missing}")
            if extra:
                details.append(f"unexpected {extra}")
            raise InvalidEvaluation(
                "scores must cover exactly the rubric criteria: " + ", ".join(details)
            )

        now = datetime.now(UTC)
        return cls(
            id=evaluation_id,
            assessor_id=assessor_id,
            content_id=content_id,
            instrument_version_id=instrument_version_id,
            result=result,
            attempt=attempt,
            occurred_at=now,
            submitted_at=now,
        )

    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None


def _count(scores: list[CriterionScore], criterion_id: str) -> int:
    return sum(1 for s in scores if s.criterion_id == criterion_id)
