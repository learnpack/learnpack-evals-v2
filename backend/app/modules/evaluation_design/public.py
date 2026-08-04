"""Public surface of Evaluation Design (ARCHITECTURE.md §3).

Today this exposes only the legacy read surface for `Rubric v1` — the reference
instrument (ADR-0015), which keeps its Rubric* names on purpose. Evaluation
stores only an instrument version id and reads the instrument through here.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.evaluation_design.application import queries as _queries
from app.modules.evaluation_design.application.dtos import CriterionDTO, RubricSnapshot
from app.modules.evaluation_design.infrastructure.repository import SqlAlchemyRubricRepository
from app.platform.uow import UnitOfWork, get_uow

__all__ = [
    "CriterionDTO",
    "RubricQueries",
    "RubricSnapshot",
    "get_rubric_queries",
]


class RubricQueries:
    """Read-only contract of Rubric Authoring."""

    def __init__(self, session: Session) -> None:
        self._rubrics = SqlAlchemyRubricRepository(session)

    def get_rubric(self, rubric_version_id: str) -> RubricSnapshot | None:
        return _queries.get_rubric(self._rubrics, rubric_version_id)


def get_rubric_queries(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> RubricQueries:
    return RubricQueries(uow.session)
