"""SQLAlchemy adapters for the Evaluation Studies ports.

Hand-mapped Core statements keep the domain free of SQLAlchemy (ARCHITECTURE.md §1).
`update` rewrites the scalar columns and replaces the child rows — the recipe/dataset are
VOs of the aggregate, not entities of their own.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.modules.evaluation_studies.application.dtos import StudyReportDTO
from app.modules.evaluation_studies.domain.model import ALL_GENERATORS, GeneratorScope, Study

_COLUMNS = (
    "id, name, description, status, instrument_version_id, assessor_id, generator_scope, "
    "created_at, opened_at, signed_off_at, signed_off_by"
)


def _scope(stored: str | None, listed: list[UUID]) -> GeneratorScope | None:
    """One column and one child table are one value (ADR-0044 §1): `all` carries no rows,
    `listed` carries the ids, and a null column is a draft that has not declared yet."""
    if stored is None:
        return None
    return tuple(listed) if stored == "listed" else ALL_GENERATORS


def _stored_scope(study: Study) -> str | None:
    """The column's half of that value."""
    if study.generator_scope is None:
        return None
    return "listed" if isinstance(study.generator_scope, tuple) else "all"


class SqlAlchemyStudyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(
        row: RowMapping,
        brief_ids: tuple[UUID, ...],
        generator_ids: list[UUID],
        content_ids: tuple[UUID, ...],
    ) -> Study:
        return Study(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            instrument_version_id=row["instrument_version_id"],
            assessor_id=row["assessor_id"],
            brief_ids=brief_ids,
            generator_scope=_scope(row["generator_scope"], generator_ids),
            content_ids=content_ids,
            created_at=row["created_at"],
            opened_at=row["opened_at"],
            signed_off_at=row["signed_off_at"],
            signed_off_by=row["signed_off_by"],
        )

    def _children_for(
        self, study_ids: list[UUID]
    ) -> tuple[dict[UUID, list[UUID]], dict[UUID, list[UUID]], dict[UUID, list[UUID]]]:
        """Three batched reads for the child rows — no N+1 (ADR-0006 spirit)."""
        recipes: dict[UUID, list[UUID]] = {}
        generators: dict[UUID, list[UUID]] = {}
        datasets: dict[UUID, list[UUID]] = {}
        if not study_ids:
            return recipes, generators, datasets
        for row in (
            self._session.execute(
                text(
                    "SELECT study_id, brief_id FROM study_recipe "
                    "WHERE study_id = ANY(:ids) ORDER BY brief_id"
                ),
                {"ids": study_ids},
            )
            .mappings()
            .all()
        ):
            recipes.setdefault(row["study_id"], []).append(row["brief_id"])
        for row in (
            self._session.execute(
                text(
                    "SELECT study_id, generator_version_id FROM study_recipe_generators "
                    "WHERE study_id = ANY(:ids) ORDER BY generator_version_id"
                ),
                {"ids": study_ids},
            )
            .mappings()
            .all()
        ):
            generators.setdefault(row["study_id"], []).append(row["generator_version_id"])
        for row in (
            self._session.execute(
                text(
                    "SELECT study_id, content_id FROM study_dataset "
                    "WHERE study_id = ANY(:ids) ORDER BY content_id"
                ),
                {"ids": study_ids},
            )
            .mappings()
            .all()
        ):
            datasets.setdefault(row["study_id"], []).append(row["content_id"])
        return recipes, generators, datasets

    def get_by_id(self, study_id: UUID) -> Study | None:
        row = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM studies WHERE id = :id"), {"id": study_id}
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        recipes, generators, datasets = self._children_for([study_id])
        return self._to_domain(
            row,
            tuple(recipes.get(study_id, [])),
            generators.get(study_id, []),
            tuple(datasets.get(study_id, [])),
        )

    def add(self, study: Study) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO studies
                    (id, name, description, status, instrument_version_id, assessor_id,
                     generator_scope)
                VALUES (:id, :name, :description, :status, :instrument_version_id,
                        :assessor_id, :generator_scope)
                """
            ),
            {
                "id": study.id,
                "name": study.name,
                "description": study.description,
                "status": study.status,
                "instrument_version_id": study.instrument_version_id,
                "assessor_id": study.assessor_id,
                "generator_scope": _stored_scope(study),
            },
        )
        self._insert_children(study)

    def update(self, study: Study) -> None:
        self._session.execute(
            text(
                """
                UPDATE studies
                   SET name = :name,
                       description = :description,
                       status = :status,
                       instrument_version_id = :instrument_version_id,
                       assessor_id = :assessor_id,
                       generator_scope = :generator_scope,
                       opened_at = :opened_at,
                       signed_off_at = :signed_off_at,
                       signed_off_by = :signed_off_by
                 WHERE id = :id
                """
            ),
            {
                "id": study.id,
                "name": study.name,
                "description": study.description,
                "status": study.status,
                "instrument_version_id": study.instrument_version_id,
                "assessor_id": study.assessor_id,
                "generator_scope": _stored_scope(study),
                "opened_at": study.opened_at,
                "signed_off_at": study.signed_off_at,
                "signed_off_by": study.signed_off_by,
            },
        )
        self._session.execute(
            text("DELETE FROM study_recipe WHERE study_id = :id"), {"id": study.id}
        )
        self._session.execute(
            text("DELETE FROM study_recipe_generators WHERE study_id = :id"), {"id": study.id}
        )
        self._session.execute(
            text("DELETE FROM study_dataset WHERE study_id = :id"), {"id": study.id}
        )
        self._insert_children(study)

    def list_all(self) -> list[Study]:
        # Newest first: the console reads this list from the top, and the study someone is
        # working on is the one just declared. `id` only breaks a tie between two rows that
        # share a `now()` — it orders nothing on its own.
        rows = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM studies ORDER BY created_at DESC, id DESC")
            )
            .mappings()
            .all()
        )
        recipes, generators, datasets = self._children_for([row["id"] for row in rows])
        return [
            self._to_domain(
                row,
                tuple(recipes.get(row["id"], [])),
                generators.get(row["id"], []),
                tuple(datasets.get(row["id"], [])),
            )
            for row in rows
        ]

    def _insert_children(self, study: Study) -> None:
        for brief_id in study.brief_ids:
            self._session.execute(
                text("INSERT INTO study_recipe (study_id, brief_id) VALUES (:sid, :bid)"),
                {"sid": study.id, "bid": brief_id},
            )
        # Rows only when the scope names versions: `all` IS the column, and writing every
        # existing version as a list would freeze an answer that is meant to be a question.
        if isinstance(study.generator_scope, tuple):
            for generator_version_id in study.generator_scope:
                self._session.execute(
                    text(
                        "INSERT INTO study_recipe_generators (study_id, generator_version_id) "
                        "VALUES (:sid, :gid)"
                    ),
                    {"sid": study.id, "gid": generator_version_id},
                )
        for content_id in study.content_ids:
            self._session.execute(
                text("INSERT INTO study_dataset (study_id, content_id) VALUES (:sid, :cid)"),
                {"sid": study.id, "cid": content_id},
            )


class SqlAlchemyStudyReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, study_id: UUID) -> StudyReportDTO | None:
        row = (
            self._session.execute(
                text(
                    "SELECT study_id, report, signed_off_at FROM study_reports WHERE study_id = :id"
                ),
                {"id": study_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return StudyReportDTO(
            study_id=row["study_id"], report=row["report"], signed_off_at=row["signed_off_at"]
        )

    def insert_once(self, study_id: UUID, report: dict[str, Any], signed_off_at: datetime) -> bool:
        """Conditional insert (ADR-0003 pattern): the report is written once, ever."""
        newly = self._session.execute(
            text(
                """
                INSERT INTO study_reports (study_id, report, signed_off_at)
                VALUES (:id, cast(:report as jsonb), :signed_off_at)
                ON CONFLICT (study_id) DO NOTHING
                RETURNING 1
                """
            ),
            {"id": study_id, "report": json.dumps(report), "signed_off_at": signed_off_at},
        ).scalar()
        return newly is not None
