"""`CourseSeat` — an evaluator's credential on the platform that serves the course. Pure Python.

The evaluation screen embeds the course, and the AI inside it will not answer without a
session belonging to a real person on that platform (ADR-0061). A seat is the identity we
create and hold so that the evaluator never has to have one: they sign in here, once, and
the session they need over there is minted for them.

**A seat is not an `Assessor`.** The assessor is who somebody is *to this product* — the
author of a judgment, one third of the triple that identifies a result (ADR-0042). The seat
is a credential elsewhere, disposable, revocable, and deliberately not the evaluator's own
account on that platform. Keeping them separate is what lets a campaign end without touching
anybody's real identity.

**Provisioning is not atomic, so the aggregate carries its own progress.** Creating a seat
takes four calls to two services; nothing rolls them back. `enrolled_at` and `ai_enrolled_at`
say which halves have happened, so an interrupted provisioning is finished rather than
started again — retrying the first call would collide with the identity it already created,
and there would be no row telling us it exists.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class SeatStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class InvalidCourseSeat(Exception):
    """The seat breaks an invariant of its aggregate."""


@dataclass
class CourseSeat:
    """Aggregate root. Identity is `id`; `assessor_id` is who it belongs to, exactly once."""

    id: UUID
    assessor_id: UUID
    # Which platform vouches for `external_subject`. Not a column named after a vendor: the
    # pair is the credential, the same shape migration 0024 settled on for `assessors`.
    provider: str
    # The membership over there — what a session is minted against.
    external_subject: str
    # The account over there. A different resource from the membership, and enrolment needs
    # this one, so both are kept rather than derived.
    external_user_id: str
    email: str
    status: SeatStatus = SeatStatus.ACTIVE
    enrolled_at: datetime | None = None
    ai_enrolled_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        # Accepts the raw string too, so the repository can hydrate straight from the DB.
        if not isinstance(self.status, SeatStatus):
            try:
                self.status = SeatStatus(self.status)
            except ValueError as exc:
                raise InvalidCourseSeat(f"unknown status: {self.status!r}") from exc

        for field in ("provider", "external_subject", "external_user_id", "email"):
            if not str(getattr(self, field) or "").strip():
                raise InvalidCourseSeat(f"a seat requires {field}")

    @property
    def is_active(self) -> bool:
        return self.status is SeatStatus.ACTIVE

    @property
    def is_ready(self) -> bool:
        """Both halves done — the only state in which a session actually carries the AI.

        Derived rather than stored: a `ready` column would be a third thing to keep true, and
        the two timestamps already say it. A seat that is not ready is not broken, it is
        unfinished, and asking this is how the caller decides whether to finish it.
        """
        return self.enrolled_at is not None and self.ai_enrolled_at is not None

    def mark_enrolled(self, now: datetime | None = None) -> bool:
        """Record that the seat belongs to the cohort that grants the AI allowance.

        Idempotent, and returns whether anything changed: the caller resumes provisioning by
        calling every step, and only the steps that had not happened should do anything.
        """
        if self.enrolled_at is not None:
            return False
        self.enrolled_at = now or datetime.now(UTC)
        return True

    def mark_ai_enabled(self, now: datetime | None = None) -> bool:
        """Record that the AI service knows this seat. Idempotent, like `mark_enrolled`."""
        if self.ai_enrolled_at is not None:
            return False
        self.ai_enrolled_at = now or datetime.now(UTC)
        return True

    def revoke(self) -> bool:
        """Take the seat out of use without deleting it. Idempotent.

        The row survives because it is the only record of which external identity we created
        for whom — the thing an operator needs to clean up over there, and the thing that
        stops a second seat being minted for somebody who already has one.
        """
        if self.status is SeatStatus.REVOKED:
            return False
        self.status = SeatStatus.REVOKED
        return True
