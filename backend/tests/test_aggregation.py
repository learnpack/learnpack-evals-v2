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
    score: int | None
    comment: str | None = None
    derived: bool = False


CONTENT = uuid4()
RUBRIC = "learnpack-pedagogical-2.0.0"


@dataclass
class FakeEvaluation:
    assessor_id: UUID
    scores: list[FakeScore]
    content_id: UUID = CONTENT
    instrument_version_id: str = RUBRIC
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


def test_an_assessor_counts_once_per_course():
    """Regression (ADR-0005): collapsing keys on (assessor, content, instrument), never
    on the assessor alone — two courses by the same evaluator both count."""
    ada = uuid4()
    evaluations = [
        evaluation(ada, content_id=CONTENT, q=4),
        evaluation(ada, content_id=uuid4(), q=5),
    ]
    assert aggregation.average_by_criterion(evaluations) == {"q": 4.5}


def test_repetitions_still_collapse_within_one_content():
    ada = uuid4()
    other_content = uuid4()
    evaluations = [
        evaluation(ada, content_id=CONTENT, submitted_at=NOW - timedelta(hours=1), q=1),
        evaluation(ada, content_id=CONTENT, submitted_at=NOW, q=4),
        evaluation(ada, content_id=other_content, q=5),
    ]
    # The superseded 1 is dropped; the two courses both count → (4 + 5) / 2
    assert aggregation.average_by_criterion(evaluations) == {"q": 4.5}


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


# ------------------------------------------------------------------------- abstentions


def test_an_abstention_is_not_averaged():
    """A null score is "I could not judge this", not a number (ADR-0052 §4)."""
    ada, bob = uuid4(), uuid4()
    evaluations = [evaluation(ada, a=4), evaluation(bob, a=None)]

    assert aggregation.average_by_criterion(evaluations) == {"a": 4.0}
    assert aggregation.dispersion_by_criterion(evaluations)["a"].rater_count == 1


def test_a_criterion_everyone_abstained_on_stays_visible_with_no_average():
    """Dropping the key would make "nobody could judge this" look like "never asked" —
    the coverage lie ADR-0011 §3 forbids. And it is None, never 0: a zero would read as
    the worst possible score."""
    ada, bob = uuid4(), uuid4()
    evaluations = [evaluation(ada, a=None), evaluation(bob, a=None)]

    averages = aggregation.average_by_criterion(evaluations)
    assert averages == {"a": None}
    assert aggregation.dispersion_by_criterion(evaluations)["a"].rater_count == 0


# --------------------------------------------------------------------------- withheld


def derived_evaluation(assessor_id: UUID, /, **scores):
    """An evaluation whose named criteria were never asked of anybody (ADR-0053)."""
    return FakeEvaluation(
        assessor_id=assessor_id,
        scores=[FakeScore(criterion_id=c, score=s, derived=True) for c, s in scores.items()],
    )


def test_a_derived_row_is_not_something_a_human_said():
    """Nobody was asked, so it is neither averaged nor counted as a rater."""
    ada = uuid4()
    evaluations = [derived_evaluation(ada, a=1)]

    assert aggregation.average_by_criterion(evaluations) == {"a": None}
    assert aggregation.dispersion_by_criterion(evaluations)["a"].rater_count == 0
    assert aggregation.withheld_criteria(evaluations) == {"a"}


def test_withheld_needs_every_row_derived_not_just_one():
    """If one assessor was asked and another was not — a content re-profiled between two
    submissions — the criterion is still one somebody judged."""
    ada, bob = uuid4(), uuid4()
    evaluations = [evaluation(ada, a=4), derived_evaluation(bob, a=1)]

    assert aggregation.withheld_criteria(evaluations) == set()
    assert aggregation.average_by_criterion(evaluations) == {"a": 4.0}


def test_an_abstention_is_not_withheld():
    """Both come back with no average, and only `withheld` tells them apart."""
    ada = uuid4()
    evaluations = [evaluation(ada, a=None)]

    assert aggregation.average_by_criterion(evaluations) == {"a": None}
    assert aggregation.withheld_criteria(evaluations) == set()
