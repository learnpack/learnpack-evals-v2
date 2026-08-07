"""Evaluation Studies' read-side DTOs and gateway-local types.

`StudyDTO`/`StudyReportDTO` are what the HTTP/CLI adapters serve. The `*Info` types are
the LOCAL translations of other modules' published language: the application layer never
imports a foreign module (architecture rule 3) — the infrastructure gateways translate
each public into these.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class StudyDTO:
    study_id: UUID
    purpose: str
    status: str
    instrument_version_id: str | None
    brief_ids: tuple[UUID, ...]
    content_ids: tuple[UUID, ...]
    created_at: datetime | None
    opened_at: datetime | None
    published_at: datetime | None
    published_by: UUID | None


@dataclass(frozen=True)
class StudyReportDTO:
    study_id: UUID
    report: dict[str, Any]
    published_at: datetime


# ------------------------------------------------- registry (evaluand side), translated


@dataclass(frozen=True)
class ContentInfo:
    content_id: UUID
    external_id: str
    package_format: str
    brief_id: UUID | None
    generator_version_id: UUID | None


@dataclass(frozen=True)
class BriefInfo:
    brief_id: UUID
    brief: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class GeneratorInfo:
    generator_version_id: UUID
    name: str
    version: str


# ------------------------------------------------- evaluation (judgment side), translated


@dataclass(frozen=True)
class ClaimJudgment:
    claim_id: str
    status: str  # supported | refuted | insufficient
    evidence_basis: dict[str, int]  # {pass, fail, noEvidence, notApplicable, notAssessed}


@dataclass(frozen=True)
class JudgmentInfo:
    judgment_id: UUID
    content_id: UUID
    derived_at: datetime
    coverage: dict[str, Any]  # {"criteria": {...}, "excludedClaims": [...]}
    claims: tuple[ClaimJudgment, ...] = ()


@dataclass(frozen=True)
class CriterionOutcomeInfo:
    """One criterion's state under a judgment — the un-aggregated form (ADR-0023 §1)."""

    judgment_id: UUID
    content_id: UUID
    criterion_id: str
    outcome: str  # pass | fail | not_applicable | no_evidence | not_assessed
    derived: bool  # the absence-derived fail (ADR-0021); counted as a fail all the same


@dataclass(frozen=True)
class FindingInfo:
    finding_id: UUID
    judgment_id: UUID
    content_id: UUID
    claim_id: str
    criterion_id: str
    failure_mode: str
    quote: str | None  # null only on absence-derived fails (ADR-0021)
    locator: dict[str, Any] | None


@dataclass(frozen=True)
class RatificationInfo:
    assessor_id: UUID
    instrument_version_id: str


# ------------------------------------------------- design (the pinned norm), translated


@dataclass(frozen=True)
class InstrumentClaim:
    claim_id: str
    statement: str
    # Criteria never reference qualities; the claim is the only bridge (12-define).
    quality_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstrumentCriterion:
    criterion_id: str
    claim_ids: tuple[str, ...]
    required_data: tuple[str, ...]
    on_missing_evidence: str


@dataclass(frozen=True)
class InstrumentInfo:
    instrument_version_id: str
    status: str
    claims: tuple[InstrumentClaim, ...] = ()
    criteria: tuple[InstrumentCriterion, ...] = ()
    # Frozen in the version at publish (ADR-0023 §8) — never the live `qualities` table,
    # whose `dimension_id` is mutable and would rewrite published studies retroactively.
    quality_dimensions: dict[str, str] = field(default_factory=dict)

    @property
    def is_published(self) -> bool:
        return self.status == "published"


# ------------------------------------------------- profiling (the supply side), translated


@dataclass(frozen=True)
class CapabilityInfo:
    package_format: str
    adapter_version: str
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    accepted: bool = False
