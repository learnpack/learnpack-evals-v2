"""`Invitation` — the act of registering a human evaluator (ADR-0049). Pure Python.

An admin does not create an account: they **invite**. The `Assessor` still comes into being
at the first login (ADR-0004), which is the only moment a credential exists; what the
invitation adds is the part that was happening outside the product — who was asked in, with
which role, and with which expertise profile.

So this aggregate holds no credential and grants nothing on its own. It is a *pending fact*
that a login can consume once, and the reason it can be modelled at all without reopening
the decision ADR-0007 took: refusing to seed an `assessors` row by email is refusing to give
a principal an identity it has not proven. An invitation is not a principal.

**`expired` is derived, never stored.** A status column that says `pending` while the clock
says otherwise is a lie waiting for a job to come and fix it; asking `expires_at` costs
nothing and is right the moment it is asked. `revoke()` therefore has a real status to write
and expiry does not.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.modules.identity.domain.assessor import Role

# How long an invitation stays redeemable. Seven days is the industry's ordinary default and
# the point is that there *is* one: an invitation that never expires is a standing key to a
# roster nobody re-reads.
DEFAULT_VALIDITY = timedelta(days=7)


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class InvalidInvitation(Exception):
    """The invitation breaks an invariant of its aggregate."""


class InvalidInvitationTransition(Exception):
    """The requested lifecycle transition is not allowed from the current state."""


def normalize_email(email: str) -> str:
    """The stored form of an address, and the form every lookup compares against.

    Case and surrounding whitespace are not part of an identity — ADR-0007 already matches
    its allowlist this way, and an invitation that fails to redeem because somebody typed a
    capital would be indistinguishable from one that was never sent.
    """
    return email.strip().lower()


@dataclass
class Invitation:
    """Aggregate root. Identity is `id`; `email` is what a login is matched against."""

    id: UUID
    email: str
    role: Role = Role.EVALUATOR
    display_name: str | None = None
    expertise: str | None = None
    invited_by: UUID | None = None
    status: InvitationStatus = InvitationStatus.PENDING
    expires_at: datetime | None = None
    # The assessor this invitation produced — set exactly when `status` is `accepted`.
    accepted_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        # Accepts the raw strings too, so the repository can hydrate straight from the DB.
        if not isinstance(self.status, InvitationStatus):
            try:
                self.status = InvitationStatus(self.status)
            except ValueError as exc:
                raise InvalidInvitation(f"unknown status: {self.status!r}") from exc
        if not isinstance(self.role, Role):
            try:
                self.role = Role(self.role)
            except ValueError as exc:
                raise InvalidInvitation(f"unknown role: {self.role!r}") from exc

        self.email = normalize_email(self.email or "")
        if not self.email:
            raise InvalidInvitation("an invitation requires an email address")
        if "@" not in self.email:
            raise InvalidInvitation(f"not an email address: {self.email!r}")
        if self.expires_at is None:
            raise InvalidInvitation("an invitation requires an expiry (ADR-0049)")

    def is_expired(self, now: datetime | None = None) -> bool:
        """Derived, so it cannot disagree with the clock. See the module docstring."""
        assert self.expires_at is not None  # guaranteed by __post_init__
        return (now or datetime.now(UTC)) >= self.expires_at

    def is_redeemable(self, now: datetime | None = None) -> bool:
        """Pending and still in time — the only state a login may consume."""
        return self.status is InvitationStatus.PENDING and not self.is_expired(now)

    def redeem(self, assessor_id: UUID, now: datetime | None = None) -> None:
        """Consume the invitation for the assessor the first login just created.

        Not idempotent on purpose: a second redemption would mean two credentials answered
        to one invitation, and the second one has no claim on the role it was granting.
        """
        if self.status is not InvitationStatus.PENDING:
            raise InvalidInvitationTransition(
                f"an invitation that is '{self.status}' cannot be redeemed"
            )
        if self.is_expired(now):
            raise InvalidInvitationTransition("this invitation expired")
        self.status = InvitationStatus.ACCEPTED
        self.accepted_by = assessor_id
        self.updated_at = datetime.now(UTC)

    def revoke(self) -> None:
        """Withdraw an invitation nobody has used. Idempotent."""
        if self.status is InvitationStatus.REVOKED:
            return
        if self.status is InvitationStatus.ACCEPTED:
            raise InvalidInvitationTransition(
                "this invitation was already accepted - the assessor exists, revoking it here "
                "would change nothing"
            )
        self.status = InvitationStatus.REVOKED
        self.updated_at = datetime.now(UTC)

    def extend(self, validity: timedelta = DEFAULT_VALIDITY, now: datetime | None = None) -> None:
        """Give a pending invitation a fresh window — what re-sending one means.

        An expired invitation is extended too: it is still `pending`, and re-sending is
        exactly the remedy someone reaches for when the window closed before the person got
        round to signing in.
        """
        if self.status is not InvitationStatus.PENDING:
            raise InvalidInvitationTransition(
                f"an invitation that is '{self.status}' cannot be re-sent"
            )
        self.expires_at = (now or datetime.now(UTC)) + validity
        self.updated_at = datetime.now(UTC)
