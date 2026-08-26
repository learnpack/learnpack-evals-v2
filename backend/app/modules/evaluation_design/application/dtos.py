"""Rubric Authoring's Published Language (07-define.md).

`RubricSnapshot` is what Evaluation and the evaluator UI consume. A published rubric version
is immutable and locked, so a snapshot is safe to hand out as-is.

Read-only module: the MVP seeds `LearnPack Pedagogical Rubric` straight to `published`
(08-code.md §9). Authoring commands — and the rich `Rubric` aggregate that guards their
invariants — are `[futuro]`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

# The one provenance this module needs to name. Content Profiling owns the vocabulary
# (`declared_structured | declared_in_content | absent`); only the third decides anything
# here, and a module never imports another's domain to learn a string.
PROVENANCE_ABSENT = "absent"


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
    # data_requirement ids from the same demand-side namespace the automated instrument uses
    # (ADR-0014), under the same name and meaning: the data this item is about. What differs
    # is the consequence — here it decides whether the item is put to a human (ADR-0053).
    required_data: list[str] = field(default_factory=list)


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
    # `{qualityId: dimensionId}` for the qualities the claims reference, frozen at publish
    # (ADR-0023 §8). Empty while draft — consumers grouping by dimension read this, never
    # the live `qualities` table, whose `dimension_id` is mutable and unversioned.
    quality_dimensions: dict[str, str] = field(default_factory=dict)

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
class RubricSummaryDTO:
    """One published reference instrument version, as a chooser needs it (ADR-0056 §4).

    Deliberately not a `RubricSnapshot`: what tells two versions apart is their identity,
    their scale and how many items they ask, not the text of every item.
    """

    rubric_version_id: str
    rubric_id: str
    version: str
    name: str
    scope: str | None
    scale_min: int
    scale_max: int
    response_format: str
    criterion_count: int


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
    # `numeric | likert` — what the five points MEAN, which the range alone cannot say
    # (ADR-0052 §3). The evaluator screen picks its control from this.
    response_format: str
    criteria: list[CriterionDTO]

    @property
    def criterion_ids(self) -> list[str]:
        """The exact set an `Evaluation` must cover (07-define.md, invariant 1)."""
        return [c.criterion_id for c in self.criteria]

    @property
    def is_published(self) -> bool:
        return self.status == "published"

    def withheld(self, provenances: Mapping[str, str]) -> dict[str, int | None]:
        """The items not put to this content's rater, each with the score to record.

        ADR-0053. `provenances` maps `data_requirement_id -> provenance` over the content's
        most recent **ok** profile; an id the profile has no entry for is simply absent from
        the mapping, which is what makes the two cases distinguishable here:

        - **no entry** — the format has no field for it (ADR-0017), nobody could have
          declared it, and the automated side derives `not_applicable`, out of the
          denominator. Recorded with **no score**: there is no answer, nothing was askable.
        - **`absent`** — the adapter looked and the course said nothing. The automated side
          derives a penalising outcome, so this one is recorded at the **scale minimum**.

        The order is the automated path's — capability first, absence second. Read the other
        way round, a course whose format cannot express objectives would be indistinguishable
        from one that omitted them.

        An empty mapping means no `ok` profile, and then nothing is withheld: an unknown fact
        is not an absent datum. It is also, harmlessly, what a profile with no entries says.

        This is the ONE definition of the rule (ADR-0053 §5). The screen decides what to ask
        from it and the submit path decides what to derive from it; if those two sets ever
        disagreed, the `Evaluation` aggregate's exact-coverage invariant would break as a
        rater pressed submit.
        """
        if not provenances:
            return {}
        withheld: dict[str, int | None] = {}
        for criterion in self.criteria:
            if any(datum not in provenances for datum in criterion.required_data):
                withheld[criterion.criterion_id] = None
            elif any(provenances[datum] == PROVENANCE_ABSENT for datum in criterion.required_data):
                withheld[criterion.criterion_id] = self.scale_min
        return withheld

    def asked(self, provenances: Mapping[str, str]) -> list[CriterionDTO]:
        """The items this content's rater actually answers — everything not withheld."""
        withheld = self.withheld(provenances)
        return [c for c in self.criteria if c.criterion_id not in withheld]
