"""Public surface of Evaluation Design (ARCHITECTURE.md §3).

Today this exposes only the read surface for the human reference instrument — the reference
instrument (ADR-0015), which keeps its Rubric* names on purpose. Evaluation
stores only an instrument version id and reads the instrument through here.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.evaluation_design.application import queries as _queries
from app.modules.evaluation_design.application.dtos import (
    BindingDTO,
    ClaimDTO,
    CriterionSpecDTO,
    DataRequirementDTO,
    InstrumentSnapshot,
    RubricItemDTO,
    RubricSnapshot,
    RubricSummaryDTO,
)
from app.modules.evaluation_design.infrastructure.repository import (
    SqlAlchemyDataRequirementRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemyRubricRepository,
)
from app.platform.uow import UnitOfWork, get_uow

# Events this module publishes — the contract subscribers rely on.
# The payload of InstrumentVersionPublished IS the full snapshot (11-connect).
INSTRUMENT_VERSION_PUBLISHED = "InstrumentVersionPublished"

__all__ = [
    "INSTRUMENT_VERSION_PUBLISHED",
    "BindingDTO",
    "ClaimDTO",
    "RubricItemDTO",
    "CriterionSpecDTO",
    "DataRequirementDTO",
    "InstrumentQueries",
    "InstrumentSnapshot",
    "RubricQueries",
    "RubricSnapshot",
    "RubricSummaryDTO",
    "get_instrument_queries",
    "get_rubric_queries",
]


class InstrumentQueries:
    """Read-only contract of Evaluation Design (`getInstrument(version)`, 11-connect)."""

    def __init__(self, session: Session) -> None:
        self._instruments = SqlAlchemyInstrumentRepository(session)
        self._data_requirements = SqlAlchemyDataRequirementRepository(session)

    def get_instrument(self, instrument_version_id: str) -> InstrumentSnapshot | None:
        return _queries.get_instrument(self._instruments, instrument_version_id)

    def list_instruments(self) -> list[InstrumentSnapshot]:
        return _queries.list_instruments(self._instruments)

    def get_data_requirements(self) -> list[DataRequirementDTO]:
        return _queries.get_data_requirements(self._data_requirements)


def get_instrument_queries(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> InstrumentQueries:
    return InstrumentQueries(uow.session)


class RubricQueries:
    """Read-only contract of Rubric Authoring."""

    def __init__(self, session: Session) -> None:
        self._rubrics = SqlAlchemyRubricRepository(session)

    def get_rubric(self, rubric_version_id: str) -> RubricSnapshot | None:
        return _queries.get_rubric(self._rubrics, rubric_version_id)

    def list_published_rubrics(self) -> list[RubricSummaryDTO]:
        """The versions a campaign may pin (ADR-0056)."""
        return _queries.list_published_rubrics(self._rubrics)


def get_rubric_queries(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> RubricQueries:
    return RubricQueries(uow.session)
