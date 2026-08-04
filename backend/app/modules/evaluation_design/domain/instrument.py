"""The Instrument aggregate — one version of the complete evidential argument.

Root = `InstrumentVersion`; it owns its `Claim`s, `Criterion`s and applicability
`TaskModelBinding`s as value objects (design 12 §Evaluation Design). Lifecycle:
`draft (editable, assistible) → published (locked) → deprecated`. Published means
immutable — any change is a new version; claim/criterion ids stay stable across
versions (the lineage loop B relies on).

Sufficiency is the per-claim decision rule (ex "assembly", 13-code-qa §7): v0 implements
only `conjunctive`; `existential`/`m_of_n` are documented vocabulary, and anything
compensatory (weights, averages) is forbidden — ADR-0011 one level up.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

STATUSES = ("draft", "published", "deprecated")
ON_MISSING_EVIDENCE = ("no_evidence", "fail")
ELIGIBLE_SOURCES = ("human", "automated")
SUFFICIENCY_RULES = ("conjunctive",)  # existential / m_of_n: vocabulary, not built yet
MAX_STATEMENT_LENGTH = 300


class InvalidInstrument(Exception):
    """The instrument violates a domain invariant."""


class InstrumentImmutable(Exception):
    """Published versions never change — bump the version instead (design 12, inv. 1)."""


@dataclass(frozen=True)
class Sufficiency:
    """How much evidence settles the claim. v0: conjunctive only —
    supported iff every evidencing criterion passes; refuted iff any fails."""

    rule: str = "conjunctive"

    def __post_init__(self) -> None:
        if self.rule not in SUFFICIENCY_RULES:
            raise InvalidInstrument(
                f"sufficiency rule '{self.rule}' is not implemented "
                f"(v0 supports: {', '.join(SUFFICIENCY_RULES)}; compensatory rules are "
                "forbidden by ADR-0011)"
            )


@dataclass(frozen=True)
class Claim:
    """A one-sentence, evaluable assertion about a quality (ADR-0013)."""

    claim_id: str
    statement: str
    quality_ids: tuple[str, ...]
    warrants: tuple[str, ...]  # framework ids that license the inference
    alternative_explanations: tuple[str, ...]
    sufficiency: Sufficiency = field(default_factory=Sufficiency)

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise InvalidInstrument("claim_id is required")
        statement = self.statement.strip()
        if not statement:
            raise InvalidInstrument(f"claim {self.claim_id}: statement is required")
        if "\n" in statement or len(statement) > MAX_STATEMENT_LENGTH:
            raise InvalidInstrument(
                f"claim {self.claim_id}: statement must be one sentence "
                f"(single line, <= {MAX_STATEMENT_LENGTH} chars) — if it needs more, "
                "it is badly decomposed (ADR-0013)"
            )
        if not self.quality_ids:
            raise InvalidInstrument(f"claim {self.claim_id}: at least one quality is required")
        if not self.warrants:
            raise InvalidInstrument(f"claim {self.claim_id}: at least one warrant is required")
        if not any(e.strip() for e in self.alternative_explanations):
            raise InvalidInstrument(
                f"claim {self.claim_id}: at least one specific alternative explanation "
                "is required (design 12, invariant 2)"
            )


@dataclass(frozen=True)
class Criterion:
    """A verifiable pass condition with enumerated failure modes (ADR-0010)."""

    criterion_id: str
    pass_condition: str
    failure_modes: tuple[str, ...]
    claim_ids: tuple[str, ...]  # which claims this criterion evidences
    required_data: tuple[str, ...]  # data_requirement ids (ADR-0014 namespace)
    statement: str | None = None
    on_missing_evidence: str = "no_evidence"
    eligible_sources: tuple[str, ...] = ("human", "automated")
    condition: dict[str, Any] | None = None  # conditional applicability via task variables

    def __post_init__(self) -> None:
        if not self.criterion_id.strip():
            raise InvalidInstrument("criterion_id is required")
        if not self.pass_condition.strip():
            raise InvalidInstrument(
                f"criterion {self.criterion_id}: a verifiable pass condition is required"
            )
        if not any(m.strip() for m in self.failure_modes):
            raise InvalidInstrument(
                f"criterion {self.criterion_id}: at least one failure mode is required "
                "(the failure IS the suggestion)"
            )
        if not self.claim_ids:
            raise InvalidInstrument(
                f"criterion {self.criterion_id}: must evidence at least one claim"
            )
        if not self.required_data:
            raise InvalidInstrument(
                f"criterion {self.criterion_id}: must declare the data it requires"
            )
        if self.on_missing_evidence not in ON_MISSING_EVIDENCE:
            raise InvalidInstrument(
                f"criterion {self.criterion_id}: on_missing_evidence must be one of "
                f"{', '.join(ON_MISSING_EVIDENCE)}"
            )
        unknown_sources = set(self.eligible_sources) - set(ELIGIBLE_SOURCES)
        if unknown_sources or not self.eligible_sources:
            raise InvalidInstrument(
                f"criterion {self.criterion_id}: eligible_sources must be a non-empty "
                f"subset of {{{', '.join(ELIGIBLE_SOURCES)}}}"
            )


@dataclass(frozen=True)
class TaskModelBinding:
    """Declared applicability per package format (designed-for, ADR-0012)."""

    package_format: str
    task_variables: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.package_format.strip():
            raise InvalidInstrument("binding package_format is required")


@dataclass
class InstrumentVersion:
    """Aggregate root. Owns claims + criteria + sufficiency + bindings — "the composite"."""

    id: str  # '{instrument_id}-{version}'
    instrument_id: str
    version: str
    name: str
    purpose: str
    claims: tuple[Claim, ...] = ()
    criteria: tuple[Criterion, ...] = ()
    bindings: tuple[TaskModelBinding, ...] = ()
    status: str = "draft"
    published_at: datetime | None = None
    published_by: UUID | None = None
    revision_author: UUID | None = None
    revision_reason: str | None = None
    assisted_by: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for attr in ("instrument_id", "version", "name", "purpose"):
            if not getattr(self, attr).strip():
                raise InvalidInstrument(f"{attr} is required")
        if self.id != f"{self.instrument_id}-{self.version}":
            raise InvalidInstrument("id must be '{instrument_id}-{version}'")
        if self.status not in STATUSES:
            raise InvalidInstrument(f"status must be one of {', '.join(STATUSES)}")
        if len({c.claim_id for c in self.claims}) != len(self.claims):
            raise InvalidInstrument("duplicate claim ids")
        if len({c.criterion_id for c in self.criteria}) != len(self.criteria):
            raise InvalidInstrument("duplicate criterion ids")

    @property
    def is_published(self) -> bool:
        return self.status == "published"

    def require_editable(self) -> None:
        """Drafts are editable; anything else is locked (invariant 1)."""
        if self.status != "draft":
            raise InstrumentImmutable(
                f"{self.id} is {self.status}: published versions never change — "
                "bump the version instead"
            )

    def publish(
        self,
        published_by: UUID,
        known_data_requirements: set[str],
        known_qualities: set[str],
        known_frameworks: set[str],
        now: datetime | None = None,
    ) -> None:
        """Atomic, human act. Enforces invariants 2-4 of design 12 §Evaluation Design.

        Deliberately does NOT require extraction capability: design stays decoupled from
        adapters; readiness informs when a study pins this version (invariant 4).
        """
        self.require_editable()
        problems: list[str] = []

        evidenced: dict[str, int] = {c.claim_id: 0 for c in self.claims}
        claim_ids = set(evidenced)
        for criterion in self.criteria:
            for claim_id in criterion.claim_ids:
                if claim_id not in claim_ids:
                    problems.append(
                        f"criterion {criterion.criterion_id} references unknown claim {claim_id}"
                    )
                else:
                    evidenced[claim_id] += 1
            missing_data = set(criterion.required_data) - known_data_requirements
            if missing_data:
                problems.append(
                    f"criterion {criterion.criterion_id} requires data outside the "
                    f"namespace: {', '.join(sorted(missing_data))}"
                )

        if not self.claims:
            problems.append("an instrument needs at least one claim")
        for claim in self.claims:
            if evidenced.get(claim.claim_id) == 0:
                problems.append(f"claim {claim.claim_id} has no evidencing criterion")
            unknown_qualities = set(claim.quality_ids) - known_qualities
            if unknown_qualities:
                problems.append(
                    f"claim {claim.claim_id} asserts about unknown qualities: "
                    f"{', '.join(sorted(unknown_qualities))}"
                )
            unknown_warrants = set(claim.warrants) - known_frameworks
            if unknown_warrants:
                problems.append(
                    f"claim {claim.claim_id} cites unknown frameworks: "
                    f"{', '.join(sorted(unknown_warrants))}"
                )

        if not self.bindings:
            problems.append("publishing requires at least one designed-for binding")

        if problems:
            raise InvalidInstrument("; ".join(problems))

        self.status = "published"
        self.published_by = published_by
        self.published_at = now or datetime.now(UTC)
