"""Ports required by identity's use cases. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.assessor import Assessor
from app.modules.identity.domain.invitation import Invitation


class AssessorRepositoryPort(Protocol):
    def get_by_credential(self, provider: str, subject: str) -> Assessor | None:
        """The pair an adapter authenticated somebody with — Clerk's `sub`, or the local
        header's (ADR-0004, ADR-0008). Which provider is the adapter's business."""
        ...

    def get_by_id(self, assessor_id: UUID) -> Assessor | None: ...

    def get_by_email(self, email: str) -> Assessor | None: ...

    def get_automated(self, name: str, version: str) -> Assessor | None:
        """The automated identity is (name, version) inside source_config (ADR-0016)."""
        ...

    def list_by_ids(self, assessor_ids: list[UUID]) -> list[Assessor]:
        """Batch lookup — reports resolve many assessorIds at once (ADR-0006)."""
        ...

    def list_all(self) -> list[Assessor]:
        """Every assessor — the admin console picks who to assign from here."""
        ...

    def count_admins(self) -> int:
        """How many humans can still administer. Demoting the last one locks the console
        for everybody, with no screen left that could undo it (ADR-0050)."""
        ...

    def add(self, assessor: Assessor) -> None: ...

    def update(self, assessor: Assessor) -> None: ...


class InvitationRepositoryPort(Protocol):
    def get(self, invitation_id: UUID) -> Invitation | None: ...

    def find_pending_by_email(self, email: str) -> Invitation | None:
        """The one a login is matched against (ADR-0049). At most one exists per address —
        the partial unique index guarantees it, the use case refuses before reaching it."""
        ...

    def list_all(self) -> list[Invitation]:
        """Every invitation, newest first — the console reads pending ones to act on and
        the rest to see what happened."""
        ...

    def list_pending(self) -> list[Invitation]:
        """Only the ones still waiting for a login, expired included: expiry is derived, so
        an expired invitation is a pending one whose window closed, not another state."""
        ...

    def add(self, invitation: Invitation) -> None: ...

    def update(self, invitation: Invitation) -> None: ...


class InvitationDispatcherPort(Protocol):
    """How an invitation reaches the person it names.

    Deliberately a port with a do-nothing adapter for now: creating the invitation in the
    identity provider is the provider's business, and putting that call inside the use case
    would make the act untestable without a network and unrepeatable without an account. The
    admin still invites in Clerk by hand until the adapter that does it lands.
    """

    def dispatch(self, invitation: Invitation) -> None: ...
