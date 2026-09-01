"""Make sure this assessor has a usable seat, finishing one that was left half-done.

**Why this commits more than once.** Everywhere else in this codebase a use case commits at
the end, once, because the whole act is one transaction. Here it cannot be: provisioning is
four calls to two external services, and no database transaction can roll those back. If the
row were written only at the end, a crash halfway would leave an identity created over there
that nothing here remembers — and the retry would ask for it again and be refused, because
the address is taken. So each external step that succeeds is made durable immediately, and
the aggregate's own timestamps say where to resume.

The seat's address and label are derived from the assessor's id, never from their name or
their email. The seat is a credential we hold, not the evaluator's identity (ADR-0061), and
sending a real person's details to another tenant would make it one.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.course_session.application.ports import (
    ExternalSeat,
    SeatProviderPort,
    SeatProvisioningFailed,
    SeatRepositoryPort,
)
from app.modules.course_session.domain import events
from app.modules.course_session.domain.seat import CourseSeat
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort

# What the template must contain for two seats to be two addresses. A template without it
# would hand every assessor the same address, and the second seat would be refused with an
# error about a duplicate that reads like a bug in the provider.
SLUG_PLACEHOLDER = "{slug}"


def seat_slug(assessor_id: UUID) -> str:
    """Short, stable, and says nothing about the human. Derived so no state has to hold it."""
    return assessor_id.hex[:8]


def seat_email(template: str, assessor_id: UUID) -> str:
    """The address of this assessor's seat, from the configured template.

    Raises rather than guessing: an unusable template is a deployment that has not been
    configured, and the caller turns that into "no session available" with the reason
    visible, which is what somebody can act on.
    """
    if not template.strip():
        raise SeatProvisioningFailed(
            "no seat email template is configured (SEAT_EMAIL_TEMPLATE), so no seat can be "
            "created for this evaluator"
        )
    if SLUG_PLACEHOLDER not in template:
        raise SeatProvisioningFailed(
            f"SEAT_EMAIL_TEMPLATE must contain {SLUG_PLACEHOLDER}, otherwise every seat "
            f"would share one address: {template!r}"
        )
    return template.replace(SLUG_PLACEHOLDER, seat_slug(assessor_id))


def seat_display_name(assessor_id: UUID) -> str:
    """A neutral label for the other platform's directory. Not the evaluator's name."""
    return f"SME Seat {seat_slug(assessor_id)}"


@dataclass(frozen=True)
class EnsureCourseSeatCommand:
    assessor_id: UUID


class EnsureCourseSeat:
    def __init__(
        self,
        seats: SeatRepositoryPort,
        provider: SeatProviderPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
        email_template: str,
    ) -> None:
        self._seats = seats
        self._provider = provider
        self._publisher = publisher
        self._uow = uow
        self._email_template = email_template

    def __call__(self, command: EnsureCourseSeatCommand) -> CourseSeat:
        seat = self._seats.get_by_assessor(command.assessor_id)
        if seat is None:
            seat = self._create(command.assessor_id)

        if not seat.is_active:
            raise SeatProvisioningFailed(
                "this evaluator's seat was revoked; grant a new one from the console"
            )

        self._finish(seat)
        return seat

    def _create(self, assessor_id: UUID) -> CourseSeat:
        """The one step that cannot be retried blindly, so its result is committed alone."""
        email = seat_email(self._email_template, assessor_id)
        external = self._provider.create_seat(email, seat_display_name(assessor_id))
        seat = CourseSeat(
            id=uuid4(),
            assessor_id=assessor_id,
            provider=external.provider,
            external_subject=external.subject,
            external_user_id=external.user_id,
            email=email,
        )
        self._seats.add(seat)
        self._publisher.publish(events.course_seat_provisioned(seat))
        self._uow.commit()
        return seat

    def _finish(self, seat: CourseSeat) -> None:
        """Run the steps that have not happened yet, and only those.

        Both guards read the aggregate rather than a flag the caller passed, so calling this
        on a finished seat costs nothing and touches neither the provider nor the outbox.
        """
        external = ExternalSeat.of(seat)

        if seat.enrolled_at is None:
            self._provider.enroll(external)
            seat.mark_enrolled()
            self._seats.update(seat)
            self._uow.commit()

        if seat.ai_enrolled_at is None:
            # The AI service verifies the seat against the platform that issued it, so it
            # needs a token rather than an id. This mints one purely to hand it over; the
            # session the caller ends up using is minted separately, and the provider
            # returns the same live token to both.
            self._provider.enable_ai(external, self._provider.mint_token(external))
            seat.mark_ai_enabled()
            self._seats.update(seat)
            self._uow.commit()
