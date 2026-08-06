"""Ports required by Evaluation's use cases.

The automated-path gateways return THIS module's domain types (`InstrumentSpec`,
`ProfileData`): foreign DTOs are translated once, at the infrastructure gateways —
the application layer never imports another module (architecture rule 3).
"""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.modules.evaluation.application.dtos import EvaluationDTO, FindingDTO, QualityJudgmentDTO
from app.modules.evaluation.domain.automated import AutomatedEvaluation
from app.modules.evaluation.domain.evaluation import Evaluation
from app.modules.evaluation.domain.judgment import ClaimJudgment, FindingDraft
from app.modules.evaluation.domain.model import CriterionOutcome, InstrumentSpec, ProfileData


class EvaluationRepositoryPort(Protocol):
    def add(self, evaluation: Evaluation) -> None: ...

    def list_for_contents(self, content_ids: list[UUID]) -> list[EvaluationDTO]:
        """Batch read: every evaluation of those contents, scores included.

        Batch on purpose — Reporting would otherwise issue one query per content (ADR-0006).
        """
        ...


class InstrumentGatewayPort(Protocol):
    """The pinned norm, translated to local types (Design's public behind it)."""

    def get_instrument(self, instrument_version_id: str) -> InstrumentSpec | None: ...


class ProfileGatewayPort(Protocol):
    """The evidence base: the content's most recent `ok` profile (ADR-0015)."""

    def get_profile(self, content_id: UUID) -> ProfileData | None: ...


class AutomatedEvaluationRepositoryPort(Protocol):
    def add(self, evaluation: AutomatedEvaluation) -> None: ...

    def next_attempt(self, assessor_id: UUID, content_id: UUID, instrument_version_id: str) -> int:
        """max(attempt)+1 for the repetition triple (ADR-0005; informational)."""
        ...

    def get_outcomes(self, evaluation_id: UUID) -> tuple[CriterionOutcome, ...]: ...


@dataclass(frozen=True)
class JudgmentRecord:
    """The derived judgment with its identities assigned, ready to persist."""

    judgment_id: UUID
    evaluation_id: UUID
    content_id: UUID
    instrument_version_id: str
    coverage: dict[str, Any]
    claims: tuple[ClaimJudgment, ...]
    findings: tuple[tuple[UUID, FindingDraft], ...]  # (finding_id, draft)


class JudgmentRepositoryPort(Protocol):
    def insert(self, record: JudgmentRecord) -> bool:
        """Conditional on evaluation_id — False when already derived (replay)."""
        ...

    def list_for_contents(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[QualityJudgmentDTO]: ...

    def list_findings_for_contents(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[FindingDTO]: ...


class RatificationRepositoryPort(Protocol):
    """The ADR-0019 act: what makes an instrument version evaluable by an assessor."""

    def insert(self, assessor_id: UUID, instrument_version_id: str, ratified_by: UUID) -> bool: ...

    def is_ratified(self, assessor_id: UUID, instrument_version_id: str) -> bool: ...

    def latest_ratified(self, assessor_id: UUID, instrument_version_ids: list[str]) -> str | None:
        """Most recently ratified among the candidates (the lineage's versions)."""
        ...


__all__ = [
    "AutomatedEvaluationRepositoryPort",
    "ClaimJudgment",
    "EvaluationRepositoryPort",
    "FindingDraft",
    "InstrumentGatewayPort",
    "JudgmentRecord",
    "JudgmentRepositoryPort",
    "ProfileGatewayPort",
    "RatificationRepositoryPort",
]
