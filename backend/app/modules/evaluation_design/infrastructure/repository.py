"""SQLAlchemy adapter for `RubricRepositoryPort`.

Reads the rubric seeded by `app.cli seed` from `docs/seed/rubric-v1.json` (08-code.md §9).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.evaluation_design.application.dtos import CriterionDTO, RubricSnapshot


class SqlAlchemyRubricRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_snapshot(self, rubric_version_id: str) -> RubricSnapshot | None:
        version = (
            self._session.execute(
                text(
                    """
                    SELECT id, rubric_id, version, name, status, scope, scale_min, scale_max
                      FROM rubric_versions
                     WHERE id = :id
                    """
                ),
                {"id": rubric_version_id},
            )
            .mappings()
            .first()
        )
        if version is None:
            return None

        criteria = (
            self._session.execute(
                text(
                    """
                    SELECT criterion_id, ord, dimension, prompt, guidance, anchor_low,
                           anchor_high, qualities, grounded_in, eligible_sources
                      FROM criteria
                     WHERE rubric_version_id = :id
                     ORDER BY ord
                    """
                ),
                {"id": rubric_version_id},
            )
            .mappings()
            .all()
        )

        return RubricSnapshot(
            rubric_version_id=version["id"],
            rubric_id=version["rubric_id"],
            version=version["version"],
            name=version["name"],
            status=version["status"],
            scope=version["scope"],
            scale_min=version["scale_min"],
            scale_max=version["scale_max"],
            criteria=[
                CriterionDTO(
                    criterion_id=row["criterion_id"],
                    order=row["ord"],
                    dimension=row["dimension"],
                    prompt=row["prompt"],
                    guidance=row["guidance"],
                    anchor_low=row["anchor_low"],
                    anchor_high=row["anchor_high"],
                    qualities=row["qualities"] or [],
                    grounded_in=row["grounded_in"] or [],
                    eligible_sources=row["eligible_sources"] or [],
                )
                for row in criteria
            ],
        )
