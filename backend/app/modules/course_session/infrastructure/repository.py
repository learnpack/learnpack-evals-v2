"""SQLAlchemy adapter for `SeatRepositoryPort` (ADR-0061).

Hand-mapped with Core statements, like every other repository here, so the domain keeps zero
SQLAlchemy imports — ARCHITECTURE.md §1.
"""

from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.modules.course_session.domain.seat import CourseSeat

_COLUMNS = (
    "id, assessor_id, provider, external_subject, external_user_id, email, status, "
    "enrolled_at, ai_enrolled_at, created_at"
)


class SqlAlchemyCourseSeatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _one(self, where: str, params: dict[str, object]) -> CourseSeat | None:
        row = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM course_seats WHERE {where}"), params
            )
            .mappings()
            .first()
        )
        return None if row is None else self._to_domain(row)

    def get_by_assessor(self, assessor_id: UUID) -> CourseSeat | None:
        return self._one("assessor_id = :v", {"v": assessor_id})

    def list_all(self) -> list[CourseSeat]:
        """Every seat, newest first — what the admin console reads."""
        rows = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM course_seats ORDER BY created_at DESC")
            )
            .mappings()
            .all()
        )
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: RowMapping) -> CourseSeat:
        return CourseSeat(
            id=row["id"],
            assessor_id=row["assessor_id"],
            provider=row["provider"],
            external_subject=row["external_subject"],
            external_user_id=row["external_user_id"],
            email=row["email"],
            status=row["status"],
            enrolled_at=row["enrolled_at"],
            ai_enrolled_at=row["ai_enrolled_at"],
            created_at=row["created_at"],
        )

    def add(self, seat: CourseSeat) -> None:
        """Fills `created_at` back from the store, so the row's own clock decides sequence."""
        stamped = self._session.execute(
            text(
                """
                INSERT INTO course_seats
                    (id, assessor_id, provider, external_subject, external_user_id, email,
                     status, enrolled_at, ai_enrolled_at)
                VALUES
                    (:id, :assessor_id, :provider, :external_subject, :external_user_id,
                     :email, :status, :enrolled_at, :ai_enrolled_at)
                RETURNING created_at
                """
            ),
            self._as_params(seat),
        ).one()
        (seat.created_at,) = stamped

    def update(self, seat: CourseSeat) -> None:
        """Only what provisioning and revocation move.

        The credential columns are absent on purpose: a seat's external identity is decided
        once, when it is created, and an UPDATE that could rewrite it would make the unique
        constraint the only thing standing between two assessors and one credential.
        """
        self._session.execute(
            text(
                """
                UPDATE course_seats
                   SET status = :status,
                       enrolled_at = :enrolled_at,
                       ai_enrolled_at = :ai_enrolled_at
                 WHERE id = :id
                """
            ),
            self._as_params(seat),
        )

    @staticmethod
    def _as_params(seat: CourseSeat) -> dict[str, object]:
        return {
            "id": seat.id,
            "assessor_id": seat.assessor_id,
            "provider": seat.provider,
            "external_subject": seat.external_subject,
            "external_user_id": seat.external_user_id,
            "email": seat.email,
            "status": str(seat.status),
            "enrolled_at": seat.enrolled_at,
            "ai_enrolled_at": seat.ai_enrolled_at,
        }
