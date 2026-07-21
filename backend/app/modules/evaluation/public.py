"""Public surface of Evaluation (ARCHITECTURE.md §3).

Two things cross this boundary: the **event** `EvaluationSubmitted` (which Orchestration's
completion policy consumes) and the **read side** — Evaluation owns the `CriterionScore`s, so
Reporting reads them from here instead of joining across modules (ADR-0006).
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.evaluation.application import queries as _queries
from app.modules.evaluation.application.dtos import CriterionScoreDTO, EvaluationDTO
from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
from app.platform.uow import UnitOfWork, get_uow

EVALUATION_SUBMITTED = "EvaluationSubmitted"

__all__ = [
    "EVALUATION_SUBMITTED",
    "CriterionScoreDTO",
    "EvaluationDTO",
    "EvaluationQueries",
    "EvaluationSubmittedFact",
    "get_evaluation_queries",
]


@dataclass(frozen=True)
class EvaluationSubmittedFact:
    """The Published Language of `EvaluationSubmitted` — what subscribers may rely on."""

    evaluation_id: UUID
    assessor_id: UUID
    content_id: UUID
    rubric_version_id: str
    mode: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EvaluationSubmittedFact":
        return cls(
            evaluation_id=UUID(payload["evaluationId"]),
            assessor_id=UUID(payload["assessorId"]),
            content_id=UUID(payload["contentId"]),
            rubric_version_id=payload["rubricVersionId"],
            mode=payload.get("mode", "human"),
        )


class EvaluationQueries:
    """Read-only contract of Evaluation."""

    def __init__(self, session: Session) -> None:
        self._evaluations = SqlAlchemyEvaluationRepository(session)

    def list_for_contents(self, content_ids: list[UUID]) -> list[EvaluationDTO]:
        """Every evaluation of those contents, scores included. Batch (ADR-0006)."""
        return _queries.list_evaluations_for_contents(self._evaluations, content_ids)


def get_evaluation_queries(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> EvaluationQueries:
    return EvaluationQueries(uow.session)
