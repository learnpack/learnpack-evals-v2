"""Domain events published by Course Session (ADR-0061).

One event, and it fires when the seat exists rather than when it is finished. The fact worth
auditing is *an external identity was created and bound to this assessor* — that is what
somebody has to go and clean up when the campaign ends, and it is true from the first call
that answers. Whether the remaining halves completed is progress on the row, readable there;
publishing it again as it advances would put the same fact in the outbox three times.

The seat's credential is carried; no token ever is. A token is a session, not a fact about
the roster, and the outbox is read by people.
"""

from app.modules.course_session.domain.seat import CourseSeat
from app.shared.domain.events import DomainEvent

COURSE_SEAT_AGGREGATE = "CourseSeat"


def _seat_event(event_type: str, seat: CourseSeat) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_type=COURSE_SEAT_AGGREGATE,
        aggregate_id=str(seat.id),
        payload={
            "seatId": str(seat.id),
            "assessorId": str(seat.assessor_id),
            "provider": seat.provider,
            "externalSubject": seat.external_subject,
            "email": seat.email,
        },
    )


def course_seat_provisioned(seat: CourseSeat) -> DomainEvent:
    """An external identity now exists for this assessor, and we are the ones holding it."""
    return _seat_event("CourseSeatProvisioned", seat)


def course_seat_revoked(seat: CourseSeat) -> DomainEvent:
    """It stops being used. The row stays — see `CourseSeat.revoke`."""
    return _seat_event("CourseSeatRevoked", seat)
