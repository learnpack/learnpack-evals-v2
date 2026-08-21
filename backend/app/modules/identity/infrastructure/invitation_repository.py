"""SQLAlchemy adapter for `InvitationRepositoryPort` (ADR-0049).

Hand-mapped with Core statements, like `SqlAlchemyAssessorRepository` next door, so the
domain keeps zero SQLAlchemy imports — ARCHITECTURE.md §1.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.identity.domain.invitation import Invitation, normalize_email

_COLUMNS = (
    "id, email, role, display_name, expertise, invited_by, status, expires_at, "
    "accepted_by, created_at, updated_at"
)


class SqlAlchemyInvitationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _one(self, where: str, params: dict) -> Invitation | None:
        row = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM assessor_invitations WHERE {where}"), params
            )
            .mappings()
            .first()
        )
        return None if row is None else self._hydrate(row)

    def get(self, invitation_id: UUID) -> Invitation | None:
        return self._one("id = :v", {"v": invitation_id})

    def find_pending_by_email(self, email: str) -> Invitation | None:
        return self._one("status = 'pending' AND lower(email) = :v", {"v": normalize_email(email)})

    def _list(self, where: str = "TRUE") -> list[Invitation]:
        rows = (
            self._session.execute(
                text(
                    f"SELECT {_COLUMNS} FROM assessor_invitations "
                    f"WHERE {where} ORDER BY created_at DESC"
                )
            )
            .mappings()
            .all()
        )
        return [self._hydrate(row) for row in rows]

    def list_all(self) -> list[Invitation]:
        return self._list()

    def list_pending(self) -> list[Invitation]:
        return self._list("status = 'pending'")

    @staticmethod
    def _hydrate(row) -> Invitation:  # noqa: ANN001 — SQLAlchemy row mapping
        return Invitation(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            display_name=row["display_name"],
            expertise=row["expertise"],
            invited_by=row["invited_by"],
            status=row["status"],
            expires_at=row["expires_at"],
            accepted_by=row["accepted_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def add(self, invitation: Invitation) -> None:
        """Fills `created_at` back from the store.

        The column has a server default and the list is ordered by it, so the row's own
        clock is the one that decides sequence. Reading it back means the response to the
        act carries the same timestamp the list will show, instead of a null that the first
        refetch quietly replaces."""
        stamped = self._session.execute(
            text(
                """
                INSERT INTO assessor_invitations
                    (id, email, role, display_name, expertise, invited_by, status,
                     expires_at, accepted_by)
                VALUES
                    (:id, :email, :role, :display_name, :expertise, :invited_by, :status,
                     :expires_at, :accepted_by)
                RETURNING created_at, updated_at
                """
            ),
            self._as_params(invitation),
        ).one()
        invitation.created_at, invitation.updated_at = stamped

    def update(self, invitation: Invitation) -> None:
        self._session.execute(
            text(
                """
                UPDATE assessor_invitations
                   SET status = :status,
                       expires_at = :expires_at,
                       accepted_by = :accepted_by,
                       updated_at = now()
                 WHERE id = :id
                """
            ),
            self._as_params(invitation),
        )

    @staticmethod
    def _as_params(invitation: Invitation) -> dict:
        return {
            "id": invitation.id,
            "email": invitation.email,
            "role": str(invitation.role),
            "display_name": invitation.display_name,
            "expertise": invitation.expertise,
            "invited_by": invitation.invited_by,
            "status": str(invitation.status),
            "expires_at": invitation.expires_at,
            "accepted_by": invitation.accepted_by,
        }
