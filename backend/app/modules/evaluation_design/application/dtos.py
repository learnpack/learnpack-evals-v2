"""Rubric Authoring's Published Language (07-define.md).

`RubricSnapshot` is what Evaluation and the evaluator UI consume. A published rubric version
is immutable and locked, so a snapshot is safe to hand out as-is.

Read-only module: the MVP seeds `LearnPack Pedagogical Rubric v1` straight to `published`
(08-code.md §9). Authoring commands — and the rich `Rubric` aggregate that guards their
invariants — are `[futuro]`.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CriterionDTO:
    criterion_id: str
    order: int
    dimension: str
    prompt: str
    guidance: str
    anchor_low: str
    anchor_high: str
    qualities: list[str]
    grounded_in: list[str]
    eligible_sources: list[str]


@dataclass(frozen=True)
class ClaimDTO:
    claim_id: str
    statement: str
    quality_ids: list[str]
    warrants: list[str]
    alternative_explanations: list[str]
    sufficiency_rule: str


@dataclass(frozen=True)
class CriterionSpecDTO:
    criterion_id: str
    statement: str | None
    pass_condition: str
    failure_modes: list[str]
    claim_ids: list[str]
    required_data: list[str]
    on_missing_evidence: str
    eligible_sources: list[str]
    condition: dict[str, Any] | None


@dataclass(frozen=True)
class BindingDTO:
    package_format: str
    task_variables: dict[str, Any]


@dataclass(frozen=True)
class InstrumentSnapshot:
    """Self-contained published language of an instrument version (11-connect)."""

    instrument_version_id: str
    instrument_id: str
    version: str
    name: str
    purpose: str
    status: str
    claims: list[ClaimDTO]
    criteria: list[CriterionSpecDTO]
    bindings: list[BindingDTO]

    @property
    def criterion_ids(self) -> list[str]:
        """The exact set an Evaluation must cover, tri-state (design 12, invariant 1)."""
        return [c.criterion_id for c in self.criteria]

    @property
    def is_published(self) -> bool:
        return self.status == "published"


@dataclass(frozen=True)
class DataRequirementDTO:
    id: str
    definition: str
    aliases: list[str]
    value_domain: dict[str, Any]  # mandatory since ADR-0020
    grounded_in: list[str]


@dataclass(frozen=True)
class RubricSnapshot:
    rubric_version_id: str
    rubric_id: str
    version: str
    name: str
    status: str
    scope: str | None
    scale_min: int
    scale_max: int
    criteria: list[CriterionDTO]

    @property
    def criterion_ids(self) -> list[str]:
        """The exact set an `Evaluation` must cover (07-define.md, invariant 1)."""
        return [c.criterion_id for c in self.criteria]

    @property
    def is_published(self) -> bool:
        return self.status == "published"
