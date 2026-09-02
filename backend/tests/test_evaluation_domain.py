"""`Evaluation` invariants (07-define.md · ADR-0005) — pure domain, no DB."""

import pytest

from app.modules.evaluation.domain.evaluation import (
    Evaluation,
    InvalidEvaluation,
    ItemScore,
)
from app.shared.domain.ids import new_id

RUBRIC_QUALITIES = [
    "objectives-observable",
    "progression-starting-point",
    "alignment-coverage",
    "alignment-assessment",
    "instruction-authentic-problems",
    "instruction-demonstration",
    "instruction-prior-knowledge",
    "coherence-logical-sequence",
    "coherence-reinforcement",
    "coherence-explicit-links",
    "progression-prerequisites",
    "progression-cognitive-demand",
]


def full_scores(**overrides) -> list[ItemScore]:
    return [ItemScore(quality_id=cid, score=overrides.get(cid, 3)) for cid in RUBRIC_QUALITIES]


def submit(scores, **kwargs) -> Evaluation:
    params = {
        "evaluation_id": new_id(),
        "assessor_id": new_id(),
        "content_id": new_id(),
        "instrument_version_id": "learnpack-pedagogical-2.0.0",
        "scores": scores,
        "rubric_quality_ids": RUBRIC_QUALITIES,
    }
    return Evaluation.submit(**(params | kwargs))


# --- invariant 1: exact coverage -------------------------------------------


def test_full_coverage_is_accepted():
    evaluation = submit(full_scores())
    assert evaluation.is_submitted
    assert len(evaluation.result.scores) == len(RUBRIC_QUALITIES)


def test_missing_an_item_is_rejected():
    with pytest.raises(InvalidEvaluation, match="missing"):
        submit(full_scores()[:-1])


def test_an_extra_item_is_rejected():
    scores = [*full_scores(), ItemScore(quality_id="made-up", score=4)]
    with pytest.raises(InvalidEvaluation, match="unexpected"):
        submit(scores)


def test_duplicated_item_is_rejected():
    scores = [*full_scores(), ItemScore(quality_id="objectives-observable", score=5)]
    with pytest.raises(InvalidEvaluation, match="duplicated"):
        submit(scores)


def test_a_rubric_without_items_is_rejected():
    with pytest.raises(InvalidEvaluation, match="no items"):
        submit([], rubric_quality_ids=[])


# --- invariant 2: score range ----------------------------------------------


@pytest.mark.parametrize("score", [0, 6, -1, 100])
def test_score_out_of_range_is_rejected(score):
    with pytest.raises(InvalidEvaluation, match="between"):
        ItemScore(quality_id="objectives-observable", score=score)


@pytest.mark.parametrize("score", [3.5, "4", True])
def test_non_integer_score_is_rejected(score):
    with pytest.raises(InvalidEvaluation, match="integer"):
        ItemScore(quality_id="objectives-observable", score=score)


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_the_whole_scale_is_accepted(score):
    assert ItemScore(quality_id="objectives-observable", score=score).score == score


def test_an_abstention_is_a_null_score():
    """ "I could not judge this" is off the scale, not at the bottom of it (ADR-0052 §4)."""
    assert ItemScore(quality_id="objectives-observable", score=None).score is None


def test_an_abstention_still_covers_its_item():
    """Exact coverage is invariant 1 and an abstention is a row like any other: the
    assessor answered about their evidence, they did not leave the item blank."""
    scores = full_scores()
    scores[0] = ItemScore(quality_id=scores[0].quality_id, score=None)

    evaluation = submit(scores)

    assert evaluation.result.score_for(scores[0].quality_id) is None
    assert len(evaluation.result.scores) == len(RUBRIC_QUALITIES)


def test_comment_is_optional():
    assert ItemScore(quality_id="objectives-observable", score=3).comment is None
    with_comment = ItemScore(quality_id="objectives-observable", score=3, comment="unclear verbs")
    assert with_comment.comment == "unclear verbs"


# --- invariants 3–4: identity and repetitions ------------------------------


def test_repetitions_of_the_same_assessor_coexist():
    """No uniqueness on (assessor, content, rubric) — ADR-0005, required by 08-code.md §11."""
    assessor_id, content_id = new_id(), new_id()

    first = submit(full_scores(), assessor_id=assessor_id, content_id=content_id)
    second = submit(full_scores(), assessor_id=assessor_id, content_id=content_id)

    assert first.id != second.id
    assert (first.assessor_id, first.content_id) == (second.assessor_id, second.content_id)


def test_attempt_can_be_recorded():
    assert submit(full_scores(), attempt=2).attempt == 2


def test_result_exposes_the_score_per_quality():
    evaluation = submit(full_scores(**{"objectives-observable": 5}))
    assert evaluation.result.score_for("objectives-observable") == 5
    assert evaluation.result.score_for("not-a-quality") is None
