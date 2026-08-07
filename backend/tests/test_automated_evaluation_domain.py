"""AutomatedEvaluation root invariants — pure domain, no DB."""

from uuid import uuid4

import pytest

from app.modules.evaluation.domain.automated import AutomatedEvaluation
from app.modules.evaluation.domain.model import (
    BindingSpec,
    ClaimSpec,
    CriterionOutcome,
    CriterionSpec,
    InstrumentSpec,
    InvalidAutomatedEvaluation,
)

INSTRUMENT = InstrumentSpec(
    instrument_version_id="qa-v1",
    instrument_id="qa",
    status="published",
    claims=(ClaimSpec(claim_id="cl-1"),),
    criteria=tuple(
        CriterionSpec(
            criterion_id=criterion_id,
            pass_condition="verifiable",
            failure_modes=("mode",),
            claim_ids=("cl-1",),
            required_data=("datum",),
        )
        for criterion_id in ("cr-1", "cr-2")
    ),
    bindings=(BindingSpec("LearnpackV1"),),
)


def complete(outcomes, **overrides):
    base = dict(
        evaluation_id=uuid4(),
        assessor_id=uuid4(),
        content_id=uuid4(),
        instrument=INSTRUMENT,
        profile_id=uuid4(),
        outcomes=outcomes,
    )
    return AutomatedEvaluation.complete(**(base | overrides))


def outcome(criterion_id, kind="pass"):
    if kind == "pass":
        return CriterionOutcome(criterion_id=criterion_id, outcome="pass", quote="q")
    return CriterionOutcome(criterion_id=criterion_id, outcome="not_assessed", derived=True)


def test_complete_requires_exact_coverage():
    with pytest.raises(InvalidAutomatedEvaluation, match="without an outcome"):
        complete((outcome("cr-1"),))
    with pytest.raises(InvalidAutomatedEvaluation, match="beyond the snapshot"):
        complete((outcome("cr-1"), outcome("cr-2"), outcome("cr-ghost", "not_assessed")))
    with pytest.raises(InvalidAutomatedEvaluation, match="duplicate"):
        complete((outcome("cr-1"), outcome("cr-1")))


def test_complete_marks_submission_and_carries_attempt():
    evaluation = complete((outcome("cr-1"), outcome("cr-2", "not_assessed")), attempt=3)
    assert evaluation.submitted_at is not None
    assert evaluation.attempt == 3
    assert evaluation.instrument_version_id == "qa-v1"
    with pytest.raises(InvalidAutomatedEvaluation, match="attempt"):
        complete((outcome("cr-1"), outcome("cr-2")), attempt=0)


def test_pass_without_quote_is_impossible_by_construction():
    with pytest.raises(InvalidAutomatedEvaluation, match="executed and quoted"):
        CriterionOutcome(criterion_id="cr-1", outcome="pass")
    with pytest.raises(InvalidAutomatedEvaluation, match="executed and quoted"):
        CriterionOutcome(criterion_id="cr-1", outcome="pass", quote="q", derived=True)


def test_executed_fail_requires_quote_but_derived_fail_does_not():
    with pytest.raises(InvalidAutomatedEvaluation, match="requires its quote"):
        CriterionOutcome(criterion_id="cr-1", outcome="fail", failure_mode="mode")
    derived = CriterionOutcome(
        criterion_id="cr-1", outcome="fail", derived=True, failure_mode="required data absent: d"
    )
    assert derived.quote is None
