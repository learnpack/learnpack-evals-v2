"""Cross-evaluator aggregation — pure functions, zero imports from other modules.

07-define.md puts the cross-evaluator aggregation (mean + inter-rater) here, in Reporting.
ADR-0006 fixes *how*: collapse repetitions to the latest per assessor, then average across
assessors; inter-rater is simple dispersion.

Everything here works structurally on anything shaped like an evaluation, so it stays
independent of the Evaluation module and is unit-testable with trivial fakes.

Only the *same* criterion is ever aggregated across assessors. Collapsing distinct criteria
into one number is forbidden (ADR-0011): the result of evaluating a content is a
per-criterion profile, not a score.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID


class ScoreLike(Protocol):
    criterion_id: str
    # Null is an abstention, not a zero: the assessor answered "I could not judge this"
    # (ADR-0052 §4). Nothing here averages one.
    score: int | None
    # True when the mechanics produced the row because the content declares nothing the item
    # could be about (ADR-0053). Nobody judged it, so nothing here counts it either.
    derived: bool


class EvaluationLike(Protocol):
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
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

    A repetition is the same assessor evaluating **the same `(content, instrumentVersion)`**
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
        key = (evaluation.assessor_id, evaluation.content_id, evaluation.instrument_version_id)
        current = latest.get(key)
        if current is None or _ordering_key(evaluation) >= _ordering_key(current):
            latest[key] = evaluation
    return list(latest.values())


def _ordering_key(evaluation: EvaluationLike) -> tuple[datetime, str]:
    # The id breaks ties deterministically when two rows share a timestamp.
    return (evaluation.submitted_at or _EPOCH, str(getattr(evaluation, "evaluation_id", "")))


def scores_by_criterion(evaluations: Sequence[EvaluationLike]) -> dict[str, list[int]]:
    """One list of scores per criterion — one entry per assessor that scored it.

    Two kinds of row are **dropped from the list while keeping their criterion in the map**:
    an abstention (null score) and a derived row (ADR-0053), neither of which anybody judged.
    A criterion nobody scored therefore stays visible with an empty list; dropping the key
    instead would make it indistinguishable from a criterion that was never part of the
    instrument, which is the coverage lie ADR-0011 §3 forbids.
    """
    grouped: dict[str, list[int]] = {}
    for evaluation in collapse_latest_per_assessor(evaluations):
        for score in evaluation.scores:
            scores = grouped.setdefault(score.criterion_id, [])
            if score.score is not None and not score.derived:
                scores.append(score.score)
    return grouped


def withheld_criteria(evaluations: Sequence[EvaluationLike]) -> set[str]:
    """The criteria no assessor was asked: every row for them is derived (ADR-0053).

    "Every", not "any": while one assessor was asked and another was not, the criterion is
    still one somebody judged. That only happens if a content is re-profiled between two
    submissions, which is rare and not a reason to hide what the first rater said.
    """
    by_criterion: dict[str, list[bool]] = {}
    for evaluation in collapse_latest_per_assessor(evaluations):
        for score in evaluation.scores:
            by_criterion.setdefault(score.criterion_id, []).append(score.derived)
    return {criterion_id for criterion_id, flags in by_criterion.items() if all(flags)}


def average_by_criterion(evaluations: Sequence[EvaluationLike]) -> dict[str, float | None]:
    """`None` where every assessor abstained — never 0, which would read as the worst score."""
    return {
        criterion_id: round(statistics.fmean(scores), 2) if scores else None
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
