"""Ports required by Evaluation Design. Implemented in infrastructure."""

from typing import Any, Protocol

from app.modules.evaluation_design.application.dtos import RubricSnapshot, RubricSummaryDTO
from app.modules.evaluation_design.domain.instrument import InstrumentVersion
from app.modules.evaluation_design.domain.reference import DataRequirement


class RubricRepositoryPort(Protocol):
    """Read surface of the human reference instrument (ADR-0015, ADR-0052)."""

    def get_snapshot(self, rubric_version_id: str) -> RubricSnapshot | None: ...

    def list_published(self) -> list[RubricSummaryDTO]:
        """Only published versions: a campaign cannot open against any other (ADR-0056 §2)."""
        ...


class InstrumentRepositoryPort(Protocol):
    def get(self, instrument_version_id: str) -> InstrumentVersion | None: ...

    def save_draft(self, instrument: InstrumentVersion) -> None: ...

    def set_published(self, instrument: InstrumentVersion) -> None: ...

    def list_all(self) -> list[InstrumentVersion]: ...


class DataRequirementRepositoryPort(Protocol):
    def get_all(self) -> dict[str, DataRequirement]: ...

    def upsert(self, requirement: DataRequirement) -> None: ...


class ReferenceDataPort(Protocol):
    """The norm-side ids publish() validates against (qualities, frameworks)."""

    def quality_dimensions(self) -> dict[str, str | None]:
        """`{qualityId: dimensionId}` — the known qualities *and* their grouping, which
        publish freezes into the version (ADR-0023 §8). One source, not two."""
        ...

    def framework_ids(self) -> set[str]: ...


class DesignAssistancePort(Protocol):
    """Drafts of claims/criteria/evidence models from purpose + frameworks + offer.

    Model-only in the first increment (13-code-qa marks): no adapter exists yet. Hard
    boundary either way: nothing produced by assistance reaches Published without a
    human act (design 12, invariant 5).
    """

    def request_drafts(
        self, purpose: str, framework_ids: list[str], offer: dict[str, Any]
    ) -> dict[str, Any]: ...
