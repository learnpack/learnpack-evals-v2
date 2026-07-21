"""Cross-evaluator aggregation (ADR-0006) — pure, no DB.

Uses tiny fakes rather than the real DTOs: `aggregation` works structurally, and that
independence from the Evaluation module is part of what is being tested.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.reporting.application import aggregation

NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


@dataclass
class FakeScore:
    criterion_id: str
    score: int
    comment: str | None = None


CONTENT = uuid4()
RUBRIC = "learnpack-pedagogical-v1"


@dataclass
class FakeEvaluation:
    assessor_id: UUID
    scores: list[FakeScore]
    content_id: UUID = CONTENT
    rubric_version_id: str = RUBRIC
    submitted_at: datetime | None = NOW
    evaluation_id: UUID = field(default_factory=uuid4)


def evaluation(
    assessor_id: UUID,
    /,
    submitted_at: datetime | None = NOW,
    content_id: UUID = CONTENT,
    **scores,
):
    return FakeEvaluation(
        assessor_id=assessor_id,
        content_id=content_id,
        submitted_at=submitted_at,
        scores=[FakeScore(criterion_id=c, score=s) for c, s in scores.items()],
    )


# --------------------------------------------------------------------------- dispersion


def test_total_agreement():
    result = aggregation.dispersion([4, 4, 4])
    assert result.stdev == 0
    assert result.mean_pairwise_abs_diff == 0
    assert result.exact_agreement_pct == 100.0
    assert result.rater_count == 3


def test_maximum_disagreement():
    result = aggregation.dispersion([1, 5])
    assert result.mean_pairwise_abs_diff == 4
    assert result.exact_agreement_pct == 0.0
    assert result.stdev == 2.0


def test_single_rater_has_no_agreement_to_measure():
    """None, not 0 — 0 would read as perfect agreement, which would be a lie."""
    result = aggregation.dispersion([4])
    assert result.stdev is None
    assert result.mean_pairwise_abs_diff is None
    assert result.exact_agreement_pct is None
    assert result.rater_count == 1


def test_no_raters():
    assert aggregation.dispersion([]).rater_count == 0


def test_three_raters_partial_agreement():
    # pairs: (3,3)=0 agree, (3,5)=2, (3,5)=2  → 1 of 3 pairs agree, mean diff 4/3
    result = aggregation.dispersion([3, 3, 5])
    assert result.exact_agreement_pct == 33.3
    assert result.mean_pairwise_abs_diff == pytest.approx(1.333, abs=0.001)


# --------------------------------------------------------------------------- collapse


def test_collapse_keeps_the_most_recent_per_assessor():
    ada = uuid4()
    older = evaluation(ada, submitted_at=NOW - timedelta(hours=1), q=2)
    newer = evaluation(ada, submitted_at=NOW, q=5)

    collapsed = aggregation.collapse_latest_per_assessor([older, newer])
    assert [e.evaluation_id for e in collapsed] == [newer.evaluation_id]


def test_collapse_is_order_independent():
    ada = uuid4()
    older = evaluation(ada, submitted_at=NOW - timedelta(hours=1), q=2)
    newer = evaluation(ada, submitted_at=NOW, q=5)

    assert aggregation.collapse_latest_per_assessor([newer, older])[0].evaluation_id == (
        newer.evaluation_id
    )


def test_collapse_does_not_touch_other_assessors():
    ada, bob = uuid4(), uuid4()
    collapsed = aggregation.collapse_latest_per_assessor(
        [evaluation(ada, q=3), evaluation(bob, q=5)]
    )
    assert {e.assessor_id for e in collapsed} == {ada, bob}


def test_collapse_of_nothing():
    assert aggregation.collapse_latest_per_assessor([]) == []


def test_the_same_assessor_on_different_contents_is_not_a_repetition():
    """A repetition is same assessor + same (content, rubric) — ADR-0005.

    Regression: keying only on the assessor made one evaluator's average collapse to a
    single course. Every test then had a single course, so nothing caught it.
    """
    ada = uuid4()
    other_content = uuid4()
    collapsed = aggregation.collapse_latest_per_assessor(
        [
            evaluation(ada, content_id=CONTENT, q=4),
            evaluation(ada, content_id=other_content, q=5),
        ]
    )
    assert len(collapsed) == 2


def test_an_assessor_average_spans_their_courses():
    ada = uuid4()
    evaluations = [
        evaluation(ada, content_id=CONTENT, q=4),
        evaluation(ada, content_id=uuid4(), q=5),
    ]
    assert aggregation.overall_average(evaluations) == 4.5


def test_repetitions_still_collapse_within_one_content():
    ada = uuid4()
    other_content = uuid4()
    evaluations = [
        evaluation(ada, content_id=CONTENT, submitted_at=NOW - timedelta(hours=1), q=1),
        evaluation(ada, content_id=CONTENT, submitted_at=NOW, q=4),
        evaluation(ada, content_id=other_content, q=5),
    ]
    # The superseded 1 is dropped; the two courses both count → (4 + 5) / 2
    assert aggregation.overall_average(evaluations) == 4.5


def test_missing_timestamps_do_not_crash():
    ada = uuid4()
    collapsed = aggregation.collapse_latest_per_assessor(
        [evaluation(ada, submitted_at=None, q=1), evaluation(ada, submitted_at=NOW, q=4)]
    )
    assert len(collapsed) == 1
    assert collapsed[0].scores[0].score == 4


# --------------------------------------------------------------------------- averages


def test_average_by_criterion_across_assessors():
    ada, bob = uuid4(), uuid4()
    evaluations = [evaluation(ada, a=4, b=2), evaluation(bob, a=5, b=3)]

    assert aggregation.average_by_criterion(evaluations) == {"a": 4.5, "b": 2.5}


def test_a_repeated_assessor_does_not_weigh_twice():
    """The whole point of collapsing before averaging (ADR-0006)."""
    ada, bob = uuid4(), uuid4()
    evaluations = [
        evaluation(ada, submitted_at=NOW - timedelta(hours=1), a=1),  # superseded
        evaluation(ada, submitted_at=NOW, a=5),  # the correction
        evaluation(bob, a=3),
    ]
    # Without collapsing this would be (1+5+3)/3 = 3.0; correct is (5+3)/2 = 4.0
    assert aggregation.average_by_criterion(evaluations) == {"a": 4.0}


def test_dispersion_by_criterion_uses_one_score_per_assessor():
    ada, bob = uuid4(), uuid4()
    evaluations = [
        evaluation(ada, submitted_at=NOW - timedelta(hours=1), a=1),
        evaluation(ada, submitted_at=NOW, a=3),
        evaluation(bob, a=3),
    ]
    result = aggregation.dispersion_by_criterion(evaluations)["a"]
    assert result.rater_count == 2
    assert result.exact_agreement_pct == 100.0


def test_overall_average_spans_every_criterion():
    ada = uuid4()
    assert aggregation.overall_average([evaluation(ada, a=4, b=5, c=3)]) == 4.0


def test_overall_average_of_nothing_is_none():
    assert aggregation.overall_average([]) is None
