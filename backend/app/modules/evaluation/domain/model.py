"""Local value objects of the automated evaluation path — pure Python.

These mirror what the Design and Profiling publics expose, as THIS module's own types:
the application layer may not import another module (architecture rule 3), so foreign
DTOs are translated once, at the infrastructure gateways, into these shapes. The domain
then works on guaranteed data — profiles arrive with their value domains already checked
(ADR-0020), so executors may assume shape.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

PROVENANCE_ABSENT = "absent"

OUTCOME_PASS = "pass"
OUTCOME_FAIL = "fail"
OUTCOME_NOT_APPLICABLE = "not_applicable"
OUTCOME_NO_EVIDENCE = "no_evidence"
OUTCOME_NOT_ASSESSED = "not_assessed"
OUTCOMES = (
    OUTCOME_PASS,
    OUTCOME_FAIL,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_NO_EVIDENCE,
    OUTCOME_NOT_ASSESSED,
)
SCORED = (OUTCOME_PASS, OUTCOME_FAIL)


class InvalidAutomatedEvaluation(Exception):
    """The automated path violates a domain invariant."""


@dataclass(frozen=True)
class CriterionSpec:
    """The normative side of one criterion, as the executor and derivation see it."""

    criterion_id: str
    pass_condition: str
    failure_modes: tuple[str, ...]
    claim_ids: tuple[str, ...]
    required_data: tuple[str, ...]
    on_missing_evidence: str = "no_evidence"
    condition: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ClaimSpec:
    claim_id: str
    sufficiency_rule: str = "conjunctive"


@dataclass(frozen=True)
class BindingSpec:
    package_format: str
    task_variables: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InstrumentSpec:
    """One instrument version, reduced to what evaluating against it requires."""

    instrument_version_id: str
    instrument_id: str
    status: str
    claims: tuple[ClaimSpec, ...]
    criteria: tuple[CriterionSpec, ...]
    bindings: tuple[BindingSpec, ...]

    @property
    def is_published(self) -> bool:
        return self.status == "published"

    @property
    def criterion_ids(self) -> frozenset[str]:
        return frozenset(c.criterion_id for c in self.criteria)


@dataclass(frozen=True)
class ProfileEntryData:
    data_requirement_id: str
    provenance: str
    value: Any = None
    quote: str | None = None
    locator: Mapping[str, Any] | None = None

    @property
    def is_absent(self) -> bool:
        return self.provenance == PROVENANCE_ABSENT


@dataclass(frozen=True)
class ProfileData:
    """An `ok` profile: the only evidence base the automated path reads (ADR-0015)."""

    profile_id: UUID
    package_format: str
    entries: Mapping[str, ProfileEntryData] = field(default_factory=dict)


@dataclass(frozen=True)
class Coverage:
    """The assessor's declared coverage over its instrument lineage (ADR-0018/0019)."""

    executes: frozenset[str]
    abstains: Mapping[str, str]  # criterion_id -> short reason

    def __post_init__(self) -> None:
        overlap = self.executes & set(self.abstains)
        if overlap:
            raise InvalidAutomatedEvaluation(
                f"coverage overlap (a criterion is executed AND abstained): "
                f"{', '.join(sorted(overlap))} (ADR-0018: disjoint union)"
            )

    @property
    def declared(self) -> frozenset[str]:
        return self.executes | frozenset(self.abstains)


@dataclass(frozen=True)
class ComputedMetric:
    metric_id: str
    value: Any


@dataclass(frozen=True)
class ExecutorResult:
    """What an executor affirms about one criterion, evidence included."""

    passed: bool
    quote: str
    locator: Mapping[str, Any] | None = None
    failure_mode: str | None = None
    metrics: tuple[ComputedMetric, ...] = ()

    def __post_init__(self) -> None:
        if not self.quote.strip():
            raise InvalidAutomatedEvaluation(
                "an executor result without a verbatim quote is not evidence (ADR-0009)"
            )
        if not self.passed and not (self.failure_mode or "").strip():
            raise InvalidAutomatedEvaluation(
                "a failing executor must name the failure mode it detected"
            )


@dataclass(frozen=True)
class CriterionOutcome:
    """One row of the exact coverage: criterion -> outcome (+ origin, ADR-0021)."""

    criterion_id: str
    outcome: str
    derived: bool = False
    quote: str | None = None
    locator: Mapping[str, Any] | None = None
    failure_mode: str | None = None
    comment: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise InvalidAutomatedEvaluation(
                f"criterion {self.criterion_id}: unknown outcome {self.outcome!r}"
            )
        if self.outcome == OUTCOME_PASS and (self.derived or not (self.quote or "").strip()):
            raise InvalidAutomatedEvaluation(
                f"criterion {self.criterion_id}: a pass is always executed and quoted (ADR-0021)"
            )
        if self.outcome == OUTCOME_FAIL and not self.derived and not (self.quote or "").strip():
            raise InvalidAutomatedEvaluation(
                f"criterion {self.criterion_id}: an executed fail requires its quote "
                "(ADR-0009; only the absence-derived fail goes quoteless, ADR-0021)"
            )
        if self.failure_mode is not None and self.outcome != OUTCOME_FAIL:
            raise InvalidAutomatedEvaluation(
                f"criterion {self.criterion_id}: failure_mode only accompanies a fail"
            )
