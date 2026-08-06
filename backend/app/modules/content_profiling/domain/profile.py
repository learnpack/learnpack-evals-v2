"""The ContentProfile aggregate — cited canonical evidence for one content version.

Root with coordinates `{content_id, adapter_version}` (design 12 §Content Profiling).
Invariants, enforced by construction:

1. Every canonical entry references an existing `DataRequirement` (Conformist to the
   Evaluation Design namespace) and carries `EvidenceProvenance` — `declared_structured |
   declared_in_content | absent`, never `inferred`; a value without a verbatim quote is
   not evidence (ADR-0009).
2. Immutable. Re-profiling with another adapter version is a new profile.
3. An explicit `absent` entry is NOT the same as no entry: declared capability + missing
   data ⇒ `absent` row; no capability ⇒ no row. The `ok` factory takes the adapter's
   capabilities and demands exactly one entry per capability, so the denominator trap is
   structurally impossible.
4. Extras never use canonical ids; they are out of contract.
5. A declared value has the shape its `DataRequirement` declares (ADR-0020). This is the
   chokepoint every adapter passes through, so a second adapter covering the same id with
   a different shape is caught here — before a mis-shaped value reaches an assessor and
   yields a cited `fail` for a defect that does not exist.

A `failed` profile records that extraction broke (package unreadable, malformed
manifest): it has an error and no entries, and is never evidence.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.shared.domain.value_domain import check_value

PROVENANCES = ("declared_structured", "declared_in_content", "absent")
STATUSES = ("ok", "failed")


class InvalidProfile(Exception):
    """The profile violates a domain invariant."""


class ExtractionError(Exception):
    """The adapter could not read the package — becomes a `failed` profile, not a crash."""


@dataclass(frozen=True)
class ProfileEntry:
    """One canonical datum: `data_requirement_id` → value + provenance + verbatim quote."""

    data_requirement_id: str
    provenance: str
    value: Any = None
    quote: str | None = None
    locator: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.data_requirement_id.strip():
            raise InvalidProfile("entry data_requirement_id is required")
        if self.provenance not in PROVENANCES:
            raise InvalidProfile(
                f"entry {self.data_requirement_id}: provenance '{self.provenance}' is not one "
                f"of {', '.join(PROVENANCES)} — `inferred` does not exist (ADR-0009)"
            )
        if self.provenance == "absent":
            if self.value is not None or self.quote is not None:
                raise InvalidProfile(
                    f"entry {self.data_requirement_id}: an absent entry carries no value and "
                    "no quote — absence is the finding"
                )
        else:
            if self.value is None:
                raise InvalidProfile(
                    f"entry {self.data_requirement_id}: a declared entry requires a value"
                )
            if not (self.quote or "").strip():
                raise InvalidProfile(
                    f"entry {self.data_requirement_id}: without a verbatim quote it is not "
                    "evidence (ADR-0009)"
                )
            if not self.locator:
                raise InvalidProfile(
                    f"entry {self.data_requirement_id}: the quote needs a locator — where in "
                    "the content it lives (ADR-0009)"
                )


@dataclass(frozen=True)
class ProfileExtra:
    """A non-canonical finding, marked as out of contract (design 12, invariant 4)."""

    name: str
    value: Any = None
    quote: str | None = None
    locator: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidProfile("extra name is required")


@dataclass(frozen=True)
class ContentProfile:
    id: UUID
    content_id: UUID
    package_format: str
    adapter_version: str
    status: str
    entries: tuple[ProfileEntry, ...] = ()
    extras: tuple[ProfileExtra, ...] = ()
    error: str | None = None
    profiled_at: datetime | None = None

    @classmethod
    def ok(
        cls,
        *,
        id: UUID,
        content_id: UUID,
        package_format: str,
        adapter_version: str,
        capabilities: frozenset[str],
        value_domains: Mapping[str, dict[str, Any]],
        entries: tuple[ProfileEntry, ...],
        extras: tuple[ProfileExtra, ...] = (),
    ) -> "ContentProfile":
        """Build a successful profile, enforcing invariants 1, 3, 4 and 5.

        `value_domains` is the namespace: since ADR-0020 every canonical id declares its
        shape, so the key set and the set of canonical ids are the same thing.
        """
        canonical_ids = frozenset(value_domains)
        unknown_capabilities = capabilities - canonical_ids
        if unknown_capabilities:
            raise InvalidProfile(
                "adapter capabilities outside the data_requirements namespace: "
                f"{', '.join(sorted(unknown_capabilities))} (Conformist — the ids are minted "
                "by Evaluation Design, ADR-0014)"
            )
        entry_ids = [e.data_requirement_id for e in entries]
        if len(entry_ids) != len(set(entry_ids)):
            raise InvalidProfile("duplicate entries for the same data requirement")
        if set(entry_ids) != set(capabilities):
            missing = capabilities - set(entry_ids)
            beyond = set(entry_ids) - capabilities
            problems = []
            if missing:
                problems.append(
                    f"capabilities without an entry: {', '.join(sorted(missing))} — declared "
                    "capability + missing data must yield an explicit `absent` entry"
                )
            if beyond:
                problems.append(
                    f"entries beyond declared capabilities: {', '.join(sorted(beyond))}"
                )
            raise InvalidProfile("; ".join(problems) + " (design 12, invariant 3)")
        # Invariant 5 (ADR-0020): a declared value has the shape its requirement declares.
        # Every entry id is a capability and every capability is canonical (checked above),
        # so the domain lookup cannot miss.
        shape_problems: list[str] = []
        for entry in entries:
            if entry.provenance == "absent":
                continue
            shape_problems.extend(
                check_value(
                    entry.value,
                    value_domains[entry.data_requirement_id],
                    entry.data_requirement_id,
                )
            )
        if shape_problems:
            raise InvalidProfile(
                "extracted values do not match their declared value domain: "
                + "; ".join(shape_problems)
                + " (ADR-0020 — the adapter and the namespace disagree on the shape)"
            )

        extra_names = [x.name for x in extras]
        if len(extra_names) != len(set(extra_names)):
            raise InvalidProfile("duplicate extras")
        canonical_extras = set(extra_names) & canonical_ids
        if canonical_extras:
            raise InvalidProfile(
                f"extras using canonical ids: {', '.join(sorted(canonical_extras))} — extras "
                "are out of contract (design 12, invariant 4)"
            )
        return cls(
            id=id,
            content_id=content_id,
            package_format=package_format,
            adapter_version=adapter_version,
            status="ok",
            entries=entries,
            extras=extras,
            profiled_at=datetime.now(UTC),
        )

    @classmethod
    def failed(
        cls,
        *,
        id: UUID,
        content_id: UUID,
        package_format: str,
        adapter_version: str,
        error: str,
    ) -> "ContentProfile":
        """Record that extraction broke. No entries: a failed profile is never evidence."""
        if not error.strip():
            raise InvalidProfile("a failed profile requires the error that broke it")
        return cls(
            id=id,
            content_id=content_id,
            package_format=package_format,
            adapter_version=adapter_version,
            status="failed",
            error=error,
            profiled_at=datetime.now(UTC),
        )
