"""Ports required by Evaluation Design. Implemented in infrastructure."""

from typing import Any, Protocol

from app.modules.evaluation_design.application.dtos import RubricSnapshot
from app.modules.evaluation_design.domain.instrument import InstrumentVersion
from app.modules.evaluation_design.domain.reference import DataRequirement


class RubricRepositoryPort(Protocol):
    """Legacy read surface of Rubric v1, the reference instrument (ADR-0015)."""

    def get_snapshot(self, rubric_version_id: str) -> RubricSnapshot | None: ...


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

    def quality_ids(self) -> set[str]: ...

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
