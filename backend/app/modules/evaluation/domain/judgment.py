"""Judgment derivation — sufficiency over the six-state outcomes (13-code §3.5 + §7.1).

Conjunctive rule (the only one built): a claim is **supported** iff every evidencing
criterion passed · **refuted** iff at least one failed (one cited counterexample refutes)
· **insufficient** otherwise (`no_evidence`/`not_assessed`/`execution_error` fall here —
ADR-0018 §4, ADR-0037 §5). Deliberate error asymmetry: conjunctive produces false
"refuted" before false "supported" — right for internal QA.

Denominator rule (ADR-0011, one level up): a claim whose evidencing criteria are ALL
`not_applicable` is excluded from the judgment (no row) and recorded in the coverage;
everything else stays in — an `execution_error` never excludes a claim: a gap in this run
must stay visible in it (ADR-0037 §5). `evidence_basis` counts all six states per claim,
so every "insufficient" is qualified by its cause. Findings: one per failing criterion —
the failure mode IS the suggestion; the absence-derived fail goes quoteless with its
mechanical mode (ADR-0021).
"""

from dataclasses import dataclass, field
from typing import Any

from app.modules.evaluation.domain.model import (
    OUTCOME_EXECUTION_ERROR,
    OUTCOME_FAIL,
    OUTCOME_NO_EVIDENCE,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_NOT_ASSESSED,
    OUTCOME_PASS,
    CriterionOutcome,
    InstrumentSpec,
    InvalidAutomatedEvaluation,
)

STATUS_SUPPORTED = "supported"
STATUS_REFUTED = "refuted"
STATUS_INSUFFICIENT = "insufficient"

_BASIS_KEYS = {
    OUTCOME_PASS: "pass",
    OUTCOME_FAIL: "fail",
    OUTCOME_NO_EVIDENCE: "noEvidence",
    OUTCOME_NOT_APPLICABLE: "notApplicable",
    OUTCOME_NOT_ASSESSED: "notAssessed",
    OUTCOME_EXECUTION_ERROR: "executionError",
}


@dataclass(frozen=True)
class ClaimJudgment:
    claim_id: str
    status: str
    evidence_basis: dict[str, int]


@dataclass(frozen=True)
class FindingDraft:
    claim_id: str
    criterion_id: str
    failure_mode: str
    quote: str | None = None  # None only on the absence-derived fail (ADR-0021)
    locator: dict[str, Any] | None = None


@dataclass(frozen=True)
class JudgmentDraft:
    """The derived judgment, before persistence gives it identity."""

    claims: tuple[ClaimJudgment, ...]
    findings: tuple[FindingDraft, ...]
    coverage: dict[str, Any] = field(default_factory=dict)


def derive_judgment(
    instrument: InstrumentSpec, outcomes: tuple[CriterionOutcome, ...]
) -> JudgmentDraft:
    by_criterion = {o.criterion_id: o for o in outcomes}
    if frozenset(by_criterion) != instrument.criterion_ids:
        raise InvalidAutomatedEvaluation(
            "judgment derivation requires the exact coverage of the snapshot"
        )

    claims: list[ClaimJudgment] = []
    excluded: list[str] = []
    for claim in instrument.claims:
        evidencing = [
            by_criterion[c.criterion_id]
            for c in instrument.criteria
            if claim.claim_id in c.claim_ids
        ]
        basis = {key: 0 for key in _BASIS_KEYS.values()}
        for outcome in evidencing:
            basis[_BASIS_KEYS[outcome.outcome]] += 1

        # Denominator rule: all-not_applicable -> out of the judgment, into coverage.
        if evidencing and all(o.outcome == OUTCOME_NOT_APPLICABLE for o in evidencing):
            excluded.append(claim.claim_id)
            continue

        claims.append(
            ClaimJudgment(
                claim_id=claim.claim_id,
                status=_conjunctive(evidencing),
                evidence_basis=basis,
            )
        )

    findings = tuple(
        FindingDraft(
            claim_id=claim_id,
            criterion_id=outcome.criterion_id,
            failure_mode=outcome.failure_mode or "",
            quote=outcome.quote,
            locator=dict(outcome.locator) if outcome.locator else None,
        )
        for outcome in outcomes
        if outcome.outcome == OUTCOME_FAIL
        for claim_id in _claims_of(instrument, outcome.criterion_id)
    )

    counts = {key: 0 for key in _BASIS_KEYS.values()}
    for outcome in outcomes:
        counts[_BASIS_KEYS[outcome.outcome]] += 1
    coverage = {
        "criteria": {
            "evaluated": counts["pass"] + counts["fail"],
            "noEvidence": counts["noEvidence"],
            "notApplicable": counts["notApplicable"],
            "notAssessed": counts["notAssessed"],
            "executionError": counts["executionError"],
        },
        "excludedClaims": excluded,
    }
    return JudgmentDraft(claims=tuple(claims), findings=findings, coverage=coverage)


def _conjunctive(evidencing: list[CriterionOutcome]) -> str:
    """Supported iff all pass · refuted iff any fail · insufficient otherwise."""
    if any(o.outcome == OUTCOME_FAIL for o in evidencing):
        return STATUS_REFUTED
    if evidencing and all(o.outcome == OUTCOME_PASS for o in evidencing):
        return STATUS_SUPPORTED
    return STATUS_INSUFFICIENT


def _claims_of(instrument: InstrumentSpec, criterion_id: str) -> tuple[str, ...]:
    for criterion in instrument.criteria:
        if criterion.criterion_id == criterion_id:
            return criterion.claim_ids
    return ()
