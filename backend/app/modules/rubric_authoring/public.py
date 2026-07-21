"""Public surface of Rubric Authoring (ARCHITECTURE.md §3).

Evaluation stores only a `rubricVersion` and reads the instrument through here
(`getRubric(version)`, 05-connect.md).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.rubric_authoring.application import queries as _queries
from app.modules.rubric_authoring.application.dtos import CriterionDTO, RubricSnapshot
from app.modules.rubric_authoring.infrastructure.repository import SqlAlchemyRubricRepository
from app.platform.uow import UnitOfWork, get_uow

# Published when a rubric version is locked. Seeded in the MVP (08-code.md §9).
RUBRIC_PUBLISHED = "RubricPublished"

__all__ = [
    "RUBRIC_PUBLISHED",
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
