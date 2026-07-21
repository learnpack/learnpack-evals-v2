"""Cross-evaluator aggregation — pure functions, zero imports from other modules.

07-define.md puts the cross-evaluator aggregation (mean + inter-rater) here, in Reporting.
ADR-0006 fixes *how*: collapse repetitions to the latest per assessor, then average across
assessors; inter-rater is simple dispersion.

Everything here works structurally on anything shaped like an evaluation, so it stays
independent of the Evaluation module and is unit-testable with trivial fakes.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID


class ScoreLike(Protocol):
    criterion_id: str
    score: int


class EvaluationLike(Protocol):
    assessor_id: UUID
    content_id: UUID
    rubric_version_id: str
    submitted_at: datetime | None
    scores: Sequence[ScoreLike]


_EPOCH = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class Dispersion:
    """Inter-rater spread for one criterion (ADR-0006).

    All fields are `None` with a single rater: there is no agreement to measure, and 0 would
    read as "perfect agreement" — a lie.
    """

    stdev: float | None
    mean_pairwise_abs_diff: float | None
    exact_agreement_pct: float | None
    rater_count: int


def collapse_latest_per_assessor[E: EvaluationLike](evaluations: Sequence[E]) -> list[E]:
    """Drop superseded repetitions, keeping the most recent one.

    A repetition is the same assessor evaluating **the same `(content, rubricVersion)`**
    more than once (ADR-0005), so that triple — not the assessor alone — is the key. A
    human re-evaluation is a **correction** that supersedes the previous one, so an assessor
    never weighs twice; consistent with the quorum, which counts distinct assessors
    (ADR-0006).

    Keying on the full triple makes this correct whatever the caller passes in: evaluations
    of one content, or every evaluation by one assessor across many contents.

    `[futuro]` Deliberate automated sampling (e.g. an `LLMJudge` run N times) needs a
    *different* aggregation for a different purpose: mean per assessor plus intra-assessor
    dispersion (self-consistency). Do not reuse this function for that.
    """
    latest: dict[tuple[UUID, UUID, str], E] = {}
    for evaluation in evaluations:
        key = (evaluation.assessor_id, evaluation.content_id, evaluation.rubric_version_id)
        current = latest.get(key)
        if current is None or _ordering_key(evaluation) >= _ordering_key(current):
            latest[key] = evaluation
    return list(latest.values())


def _ordering_key(evaluation: EvaluationLike) -> tuple[datetime, str]:
    # The id breaks ties deterministically when two rows share a timestamp.
    return (evaluation.submitted_at or _EPOCH, str(getattr(evaluation, "evaluation_id", "")))


def scores_by_criterion(evaluations: Sequence[EvaluationLike]) -> dict[str, list[int]]:
    """One list of scores per criterion — one entry per assessor. Collapses first."""
    grouped: dict[str, list[int]] = {}
    for evaluation in collapse_latest_per_assessor(evaluations):
        for score in evaluation.scores:
            grouped.setdefault(score.criterion_id, []).append(score.score)
    return grouped


def average_by_criterion(evaluations: Sequence[EvaluationLike]) -> dict[str, float]:
    return {
        criterion_id: round(statistics.fmean(scores), 2)
        for criterion_id, scores in scores_by_criterion(evaluations).items()
    }


def dispersion_by_criterion(evaluations: Sequence[EvaluationLike]) -> dict[str, Dispersion]:
    return {
        criterion_id: dispersion(scores)
        for criterion_id, scores in scores_by_criterion(evaluations).items()
    }


def dispersion(scores: Sequence[int]) -> Dispersion:
    """Spread among raters for one criterion."""
    count = len(scores)
    if count < 2:
        return Dispersion(
            stdev=None, mean_pairwise_abs_diff=None, exact_agreement_pct=None, rater_count=count
        )

    pairs = [(scores[i], scores[j]) for i in range(count) for j in range(i + 1, count)]
    agreeing = sum(1 for a, b in pairs if a == b)

    return Dispersion(
        # Population stdev: these raters *are* the whole set, not a sample of one.
        stdev=round(statistics.pstdev(scores), 3),
        mean_pairwise_abs_diff=round(statistics.fmean([abs(a - b) for a, b in pairs]), 3),
        exact_agreement_pct=round(100 * agreeing / len(pairs), 1),
        rater_count=count,
    )


def overall_average(evaluations: Sequence[EvaluationLike]) -> float | None:
    """Mean across every criterion of every (collapsed) evaluation."""
    all_scores = [
        score.score
        for evaluation in collapse_latest_per_assessor(evaluations)
        for score in evaluation.scores
    ]
    if not all_scores:
        return None
    return round(statistics.fmean(all_scores), 2)
