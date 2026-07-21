"""SQLAlchemy adapter for `AssessorRepositoryPort`.

Aggregates are mapped by hand (Core statements) instead of declarative ORM models, so the
domain keeps zero SQLAlchemy imports — ARCHITECTURE.md §1.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.identity.domain.assessor import Assessor

_COLUMNS = "id, clerk_user_id, email, display_name, role, expertise"


class SqlAlchemyAssessorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _one(self, where: str, params: dict) -> Assessor | None:
        row = (
            self._session.execute(text(f"SELECT {_COLUMNS} FROM assessors WHERE {where}"), params)
            .mappings()
            .first()
        )
        if row is None:
            return None
        return Assessor(
            id=row["id"],
            clerk_user_id=row["clerk_user_id"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            expertise=row["expertise"],
        )

    def get_by_clerk_user_id(self, clerk_user_id: str) -> Assessor | None:
        return self._one("clerk_user_id = :v", {"v": clerk_user_id})

    def get_by_id(self, assessor_id: UUID) -> Assessor | None:
        return self._one("id = :v", {"v": assessor_id})

    def get_by_email(self, email: str) -> Assessor | None:
        return self._one("lower(email) = lower(:v)", {"v": email})

    def list_by_ids(self, assessor_ids: list[UUID]) -> list[Assessor]:
        if not assessor_ids:
            return []
        rows = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM assessors WHERE id = ANY(:ids)"),
                {"ids": assessor_ids},
            )
            .mappings()
            .all()
        )
        return [
            Assessor(
                id=row["id"],
                clerk_user_id=row["clerk_user_id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                expertise=row["expertise"],
            )
            for row in rows
        ]

    def add(self, assessor: Assessor) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO assessors (id, clerk_user_id, email, display_name, role, expertise)
                VALUES (:id, :clerk_user_id, :email, :display_name, :role, :expertise)
                """
            ),
            self._as_params(assessor),
        )

    def update(self, assessor: Assessor) -> None:
        self._session.execute(
            text(
                """
                UPDATE assessors
                   SET email = :email,
                       display_name = :display_name,
                       role = :role,
                       expertise = :expertise
                 WHERE id = :id
                """
            ),
            self._as_params(assessor),
        )

    @staticmethod
    def _as_params(assessor: Assessor) -> dict:
        return {
            "id": assessor.id,
            "clerk_user_id": assessor.clerk_user_id,
            "email": assessor.email,
            "display_name": assessor.display_name,
            "role": str(assessor.role),
            "expertise": assessor.expertise,
        }
