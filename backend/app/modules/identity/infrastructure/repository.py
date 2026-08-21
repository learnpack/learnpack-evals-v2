"""SQLAlchemy adapter for `AssessorRepositoryPort`.

Aggregates are mapped by hand (Core statements) instead of declarative ORM models, so the
domain keeps zero SQLAlchemy imports — ARCHITECTURE.md §1.
"""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.identity.domain.assessor import Assessor

_COLUMNS = (
    "id, auth_provider, auth_subject, email, display_name, role, expertise, kind, "
    "status, source_config"
)


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
        return self._hydrate(row)

    def get_by_credential(self, provider: str, subject: str) -> Assessor | None:
        return self._one("auth_provider = :p AND auth_subject = :s", {"p": provider, "s": subject})

    def get_by_id(self, assessor_id: UUID) -> Assessor | None:
        return self._one("id = :v", {"v": assessor_id})

    def get_by_email(self, email: str) -> Assessor | None:
        return self._one("lower(email) = lower(:v)", {"v": email})

    def get_automated(self, name: str, version: str) -> Assessor | None:
        """The automated identity is (name, version) inside source_config (ADR-0016)."""
        return self._one(
            "kind = 'automated' AND source_config->>'name' = :name "
            "AND source_config->>'version' = :version",
            {"name": name, "version": version},
        )

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
        return [self._hydrate(row) for row in rows]

    def list_all(self) -> list[Assessor]:
        rows = (
            self._session.execute(text(f"SELECT {_COLUMNS} FROM assessors ORDER BY created_at"))
            .mappings()
            .all()
        )
        return [self._hydrate(row) for row in rows]

    def count_admins(self) -> int:
        """Counted in the store rather than over `list_all()`: this decides a refusal, and
        it must see the rows as they are, not as a page load once saw them."""
        return int(
            self._session.execute(
                text(
                    "SELECT count(*) FROM assessors "
                    "WHERE kind = 'human' AND role = 'admin' AND status = 'active'"
                )
            ).scalar_one()
        )

    @staticmethod
    def _hydrate(row) -> Assessor:  # noqa: ANN001 — SQLAlchemy row mapping
        return Assessor(
            id=row["id"],
            auth_provider=row["auth_provider"],
            auth_subject=row["auth_subject"],
            email=row["email"],
            display_name=row["display_name"],
            role=row["role"],
            expertise=row["expertise"],
            kind=row["kind"],
            status=row["status"],
            source_config=row["source_config"],
        )

    def add(self, assessor: Assessor) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO assessors
                    (id, auth_provider, auth_subject, email, display_name, role, expertise,
                     kind, status, source_config)
                VALUES
                    (:id, :auth_provider, :auth_subject, :email, :display_name, :role,
                     :expertise, :kind, :status, cast(:source_config as jsonb))
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
                       expertise = :expertise,
                       status = :status
                 WHERE id = :id
                """
            ),
            self._as_params(assessor),
        )

    @staticmethod
    def _as_params(assessor: Assessor) -> dict:
        return {
            "id": assessor.id,
            "auth_provider": assessor.auth_provider,
            "auth_subject": assessor.auth_subject,
            "email": assessor.email,
            "display_name": assessor.display_name,
            "role": str(assessor.role),
            "expertise": assessor.expertise,
            "kind": str(assessor.kind),
            "status": str(assessor.status),
            "source_config": (
                json.dumps(assessor.source_config) if assessor.source_config is not None else None
            ),
        }
