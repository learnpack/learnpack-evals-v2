"""SQLAlchemy adapter for `EvaluationRepositoryPort`."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.evaluation.application.dtos import CriterionScoreDTO, EvaluationDTO
from app.modules.evaluation.domain.evaluation import Evaluation


class SqlAlchemyEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, evaluation: Evaluation) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO evaluations
                    (id, assessor_id, content_id, rubric_version_id, attempt,
                     occurred_at, submitted_at)
                VALUES (:id, :assessor_id, :content_id, :rubric, :attempt,
                        :occurred_at, :submitted_at)
                """
            ),
            {
                "id": evaluation.id,
                "assessor_id": evaluation.assessor_id,
                "content_id": evaluation.content_id,
                "rubric": evaluation.rubric_version_id,
                "attempt": evaluation.attempt,
                "occurred_at": evaluation.occurred_at,
                "submitted_at": evaluation.submitted_at,
            },
        )
        for score in evaluation.result.scores:
            self._session.execute(
                text(
                    """
                    INSERT INTO criterion_scores (evaluation_id, criterion_id, score, comment)
                    VALUES (:evaluation_id, :criterion_id, :score, :comment)
                    """
                ),
                {
                    "evaluation_id": evaluation.id,
                    "criterion_id": score.criterion_id,
                    "score": score.score,
                    "comment": score.comment,
                },
            )

    def list_for_contents(self, content_ids: list[UUID]) -> list[EvaluationDTO]:
        """Two queries regardless of how many contents — never one per content (ADR-0006)."""
        if not content_ids:
            return []

        rows = (
            self._session.execute(
                text(
                    """
                    SELECT id, assessor_id, content_id, rubric_version_id, attempt, submitted_at
                      FROM evaluations
                     WHERE content_id = ANY(:content_ids)
                     ORDER BY submitted_at, id
                    """
                ),
                {"content_ids": content_ids},
            )
            .mappings()
            .all()
        )
        if not rows:
            return []

        score_rows = (
            self._session.execute(
                text(
                    """
                    SELECT evaluation_id, criterion_id, score, comment
                      FROM criterion_scores
                     WHERE evaluation_id = ANY(:evaluation_ids)
                     ORDER BY criterion_id
                    """
                ),
                {"evaluation_ids": [row["id"] for row in rows]},
            )
            .mappings()
            .all()
        )

        by_evaluation: dict[UUID, list[CriterionScoreDTO]] = defaultdict(list)
        for score in score_rows:
            by_evaluation[score["evaluation_id"]].append(
                CriterionScoreDTO(
                    criterion_id=score["criterion_id"],
                    score=score["score"],
                    comment=score["comment"],
                )
            )

        return [
            EvaluationDTO(
                evaluation_id=row["id"],
                assessor_id=row["assessor_id"],
                content_id=row["content_id"],
                rubric_version_id=row["rubric_version_id"],
                attempt=row["attempt"],
                submitted_at=row["submitted_at"],
                scores=by_evaluation.get(row["id"], []),
            )
            for row in rows
        ]
