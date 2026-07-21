"""Read-only query port of Evaluation.

Evaluation owns the `CriterionScore`s, so it is the only module that may serve them
(ADR-0006: Reporting composes through query ports, it does not JOIN across modules).
"""

from uuid import UUID

from app.modules.evaluation.application.dtos import EvaluationDTO
from app.modules.evaluation.application.ports import EvaluationRepositoryPort


def list_evaluations_for_contents(
    evaluations: EvaluationRepositoryPort, content_ids: list[UUID]
) -> list[EvaluationDTO]:
    if not content_ids:
        return []
    return evaluations.list_for_contents(content_ids)
