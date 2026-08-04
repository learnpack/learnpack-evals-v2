"""`Evaluation` invariants (07-define.md · ADR-0005) — pure domain, no DB."""

import pytest

from app.modules.evaluation.domain.evaluation import (
    CriterionScore,
    Evaluation,
    InvalidEvaluation,
)
from app.shared.domain.ids import new_id

RUBRIC_CRITERIA = [
    "objectives-quality",
    "constructive-alignment",
    "instructional-design",
    "inter-lesson-coherence",
    "learning-progression",
]


def full_scores(**overrides) -> list[CriterionScore]:
    return [
        CriterionScore(criterion_id=cid, score=overrides.get(cid, 3)) for cid in RUBRIC_CRITERIA
    ]


def submit(scores, **kwargs) -> Evaluation:
    params = {
        "evaluation_id": new_id(),
        "assessor_id": new_id(),
        "content_id": new_id(),
        "instrument_version_id": "learnpack-pedagogical-v1",
        "scores": scores,
        "rubric_criterion_ids": RUBRIC_CRITERIA,
    }
    return Evaluation.submit(**(params | kwargs))


# --- invariant 1: exact coverage -------------------------------------------


def test_full_coverage_is_accepted():
    evaluation = submit(full_scores())
    assert evaluation.is_submitted
    assert len(evaluation.result.scores) == 5


def test_missing_a_criterion_is_rejected():
    with pytest.raises(InvalidEvaluation, match="missing"):
        submit(full_scores()[:-1])


def test_an_extra_criterion_is_rejected():
    scores = [*full_scores(), CriterionScore(criterion_id="made-up", score=4)]
    with pytest.raises(InvalidEvaluation, match="unexpected"):
        submit(scores)


def test_duplicated_criterion_is_rejected():
    scores = [*full_scores(), CriterionScore(criterion_id="objectives-quality", score=5)]
    with pytest.raises(InvalidEvaluation, match="duplicated"):
        submit(scores)


def test_a_rubric_without_criteria_is_rejected():
    with pytest.raises(InvalidEvaluation, match="no criteria"):
        submit([], rubric_criterion_ids=[])


# --- invariant 2: score range ----------------------------------------------


@pytest.mark.parametrize("score", [0, 6, -1, 100])
def test_score_out_of_range_is_rejected(score):
    with pytest.raises(InvalidEvaluation, match="between"):
        CriterionScore(criterion_id="objectives-quality", score=score)


@pytest.mark.parametrize("score", [3.5, "4", None, True])
def test_non_integer_score_is_rejected(score):
    with pytest.raises(InvalidEvaluation, match="integer"):
        CriterionScore(criterion_id="objectives-quality", score=score)


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_the_whole_scale_is_accepted(score):
    assert CriterionScore(criterion_id="objectives-quality", score=score).score == score


def test_comment_is_optional():
    assert CriterionScore(criterion_id="objectives-quality", score=3).comment is None
    with_comment = CriterionScore(
        criterion_id="objectives-quality", score=3, comment="unclear verbs"
    )
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


def test_result_exposes_the_score_per_criterion():
    evaluation = submit(full_scores(**{"objectives-quality": 5}))
    assert evaluation.result.score_for("objectives-quality") == 5
    assert evaluation.result.score_for("not-a-criterion") is None
