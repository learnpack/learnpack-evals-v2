"""Ports of Evaluation Studies. Repositories persist the aggregate; the gateway ports are
the local face of other modules' publics (implemented in infrastructure/gateways.py)."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.modules.evaluation_studies.application.dtos import (
    BriefInfo,
    CapabilityInfo,
    ContentInfo,
    CriterionOutcomeInfo,
    FindingInfo,
    GeneratorInfo,
    InstrumentInfo,
    JudgmentInfo,
    RatificationInfo,
    StudyReportDTO,
)
from app.modules.evaluation_studies.domain.model import Study


class StudyRepositoryPort(Protocol):
    def get_by_id(self, study_id: UUID) -> Study | None: ...

    def add(self, study: Study) -> None: ...

    def update(self, study: Study) -> None: ...

    def list_all(self) -> list[Study]: ...


class StudyReportRepositoryPort(Protocol):
    def get(self, study_id: UUID) -> StudyReportDTO | None: ...

    def insert_once(self, study_id: UUID, report: dict[str, Any], published_at: datetime) -> bool:
        """True if newly written; False if a report already exists (publish is once)."""
        ...


class RegistryGatewayPort(Protocol):
    def get_contents_by_briefs(self, brief_ids: list[UUID]) -> list[ContentInfo]: ...

    def get_contents_by_ids(self, content_ids: list[UUID]) -> list[ContentInfo]: ...

    def get_brief(self, brief_id: UUID) -> BriefInfo | None: ...

    def get_generator(self, generator_version_id: UUID) -> GeneratorInfo | None: ...


class EvaluationGatewayPort(Protocol):
    def get_judgments(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[JudgmentInfo]: ...

    def get_findings(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[FindingInfo]: ...

    def get_criterion_outcomes(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[CriterionOutcomeInfo]: ...

    def list_ratifications(self, instrument_version_id: str) -> list[RatificationInfo]: ...


class DesignGatewayPort(Protocol):
    def get_instrument(self, instrument_version_id: str) -> InstrumentInfo | None: ...


class ProfilingGatewayPort(Protocol):
    def get_capabilities(self, package_format: str) -> CapabilityInfo | None: ...
