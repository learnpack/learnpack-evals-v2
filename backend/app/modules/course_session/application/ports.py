"""Ports required by Course Session's use cases. Implemented in infrastructure."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.course_session.domain.seat import CourseSeat


@dataclass(frozen=True)
class ExternalSeat:
    """The identity a provider created, as the provider itself names it.

    `provider` travels in here rather than being asked of the port separately, because the
    only thing that can truthfully say which platform vouches for a subject is the adapter
    that talked to it. Two ids because they are two resources over there: `subject` is the
    membership a session is minted against, `user_id` the account that gets enrolled.
    """

    provider: str
    subject: str
    user_id: str

    @classmethod
    def of(cls, seat: CourseSeat) -> "ExternalSeat":
        """The external half of a seat we already hold."""
        return cls(
            provider=seat.provider,
            subject=seat.external_subject,
            user_id=seat.external_user_id,
        )


class SeatRepositoryPort(Protocol):
    def get_by_assessor(self, assessor_id: UUID) -> CourseSeat | None:
        """The seat held for this person, or none yet. At most one exists — the unique
        constraint guarantees it, the use case never tries for a second."""
        ...

    def add(self, seat: CourseSeat) -> None: ...

    def update(self, seat: CourseSeat) -> None: ...


class SeatProvisioningFailed(Exception):
    """A step of provisioning did not complete, naming which one and why.

    Never a reason to lose what already happened: the seat row records the steps that did
    complete, so the remedy is to run the act again rather than to start a second seat.
    """


class SeatProviderPort(Protocol):
    """The platform that serves the course, from the outside.

    Four acts rather than one `provision()`, because they fail independently and each one
    that succeeded must stay succeeded — the aggregate records them one at a time so an
    interrupted provisioning is finished, not restarted.
    """

    def create_seat(self, email: str, display_name: str) -> ExternalSeat:
        """Create the identity. The only step that is not safe to repeat blindly: a second
        call for the same address is refused over there, which is why its result is
        persisted before anything else runs."""
        ...

    def enroll(self, seat: ExternalSeat) -> None:
        """Give the seat the standing that grants its AI allowance."""
        ...

    def mint_token(self, seat: ExternalSeat) -> str:
        """A short-lived credential for this seat. Callers must not log or store it."""
        ...

    def enable_ai(self, seat: ExternalSeat, token: str) -> None:
        """Register the seat with the AI service, using a token it can verify upstream."""
        ...
