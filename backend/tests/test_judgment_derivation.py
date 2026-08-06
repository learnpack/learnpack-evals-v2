"""Judgment derivation — conjunctive sufficiency over five states, pure domain."""

import pytest

from app.modules.evaluation.domain.judgment import derive_judgment
from app.modules.evaluation.domain.model import (
    BindingSpec,
    ClaimSpec,
    CriterionOutcome,
    CriterionSpec,
    InstrumentSpec,
    InvalidAutomatedEvaluation,
)


def instrument(criteria_claims: dict[str, tuple[str, ...]]) -> InstrumentSpec:
    """criteria_claims: criterion_id -> claim_ids it evidences."""
    claim_ids = sorted({c for claims in criteria_claims.values() for c in claims})
    return InstrumentSpec(
        instrument_version_id="qa-v1",
        instrument_id="qa",
        status="published",
        claims=tuple(ClaimSpec(claim_id=c) for c in claim_ids),
        criteria=tuple(
            CriterionSpec(
                criterion_id=criterion_id,
                pass_condition="verifiable",
                failure_modes=("mode",),
                claim_ids=claims,
                required_data=("datum",),
            )
            for criterion_id, claims in criteria_claims.items()
        ),
        bindings=(BindingSpec("LearnpackV1"),),
    )


def outcome(criterion_id: str, kind: str, **overrides) -> CriterionOutcome:
    presets = {
        "pass": dict(outcome="pass", quote="q", locator={"a": "b"}),
        "fail": dict(outcome="fail", quote="q", failure_mode="mode"),
        "derived_fail": dict(
            outcome="fail", derived=True, failure_mode="required data absent: datum"
        ),
        "no_evidence": dict(outcome="no_evidence", derived=True),
        "not_applicable": dict(outcome="not_applicable", derived=True),
        "not_assessed": dict(outcome="not_assessed", derived=True),
    }
    return CriterionOutcome(criterion_id=criterion_id, **(presets[kind] | overrides))


def test_supported_iff_every_evidencing_criterion_passes():
    draft = derive_judgment(
        instrument({"cr-1": ("cl-a",), "cr-2": ("cl-a",)}),
        (outcome("cr-1", "pass"), outcome("cr-2", "pass")),
    )
    assert draft.claims[0].status == "supported"
    assert draft.claims[0].evidence_basis["pass"] == 2


def test_one_cited_counterexample_refutes():
    draft = derive_judgment(
        instrument({"cr-1": ("cl-a",), "cr-2": ("cl-a",)}),
        (outcome("cr-1", "pass"), outcome("cr-2", "fail")),
    )
    assert draft.claims[0].status == "refuted"


@pytest.mark.parametrize("state", ["no_evidence", "not_assessed", "not_applicable"])
def test_anything_short_of_full_pass_is_insufficient(state):
    draft = derive_judgment(
        instrument({"cr-1": ("cl-a",), "cr-2": ("cl-a",)}),
        (outcome("cr-1", "pass"), outcome("cr-2", state)),
    )
    assert draft.claims[0].status == "insufficient"
    # The cause is visible in the basis (ADR-0018: every insufficient is qualified).
    key = {
        "no_evidence": "noEvidence",
        "not_assessed": "notAssessed",
        "not_applicable": "notApplicable",
    }
    assert draft.claims[0].evidence_basis[key[state]] == 1


def test_all_not_applicable_claim_is_excluded_and_recorded_in_coverage():
    draft = derive_judgment(
        instrument({"cr-1": ("cl-a",), "cr-2": ("cl-b",)}),
        (outcome("cr-1", "not_applicable"), outcome("cr-2", "pass")),
    )
    assert [c.claim_id for c in draft.claims] == ["cl-b"]  # cl-a out of the denominator
    assert draft.coverage["excludedClaims"] == ["cl-a"]
    assert draft.coverage["criteria"] == {
        "evaluated": 1,
        "noEvidence": 0,
        "notApplicable": 1,
        "notAssessed": 0,
    }


def test_derived_fail_refutes_and_produces_a_quoteless_finding():
    draft = derive_judgment(instrument({"cr-1": ("cl-a",)}), (outcome("cr-1", "derived_fail"),))
    assert draft.claims[0].status == "refuted"
    finding = draft.findings[0]
    assert finding.quote is None  # ADR-0021: the absence is the finding
    assert finding.failure_mode == "required data absent: datum"


def test_executed_fail_produces_a_cited_finding_per_evidenced_claim():
    draft = derive_judgment(
        instrument({"cr-1": ("cl-a", "cl-b")}),
        (outcome("cr-1", "fail", quote="the offending text"),),
    )
    assert {(f.claim_id, f.criterion_id) for f in draft.findings} == {
        ("cl-a", "cr-1"),
        ("cl-b", "cr-1"),
    }
    assert all(f.quote == "the offending text" for f in draft.findings)


def test_derivation_requires_the_exact_coverage():
    with pytest.raises(InvalidAutomatedEvaluation, match="exact coverage"):
        derive_judgment(
            instrument({"cr-1": ("cl-a",), "cr-2": ("cl-a",)}), (outcome("cr-1", "pass"),)
        )
