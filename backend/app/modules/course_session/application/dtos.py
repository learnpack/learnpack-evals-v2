"""Published Language of Course Session — what other modules and the API may read.

`CourseSessionDTO` deliberately carries no seat: which external identity was used is our
bookkeeping, not the caller's, and the only thing a course page needs is whether it got a
session and, when it did not, a sentence explaining why.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CourseSeatDTO:
    """A seat as the admin console reads it. No token: a session is not part of a roster."""

    seat_id: UUID
    assessor_id: UUID
    provider: str
    email: str
    status: str
    is_ready: bool
    created_at: datetime | None


@dataclass(frozen=True)
class CourseSessionDTO:
    """The answer to "can this person use the course's AI right now".

    `token` is `None` exactly when `reason` is set. Both together would be a contradiction,
    and neither would leave the caller unable to say anything to the human waiting.
    """

    token: str | None
    reason: str | None = None

    @property
    def granted(self) -> bool:
        return self.token is not None
