"""`Assignment` — a small aggregate with its own lifecycle (ADR-0002). Pure Python.

An invitation for an `Assessor` to evaluate a `Content` within a campaign. It is the **unit of
human anti-duplication**: at most one active assignment per `(campaign, content, assessor)`,
satisfied by **one** submission (ADR-0005). Reassign = cancel + a new one.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class AssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    OPENED = "opened"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


class InvalidAssignmentTransition(Exception):
    """The requested lifecycle transition is not allowed from the current status."""


# Assigned → Opened → Submitted, with Cancelled reachable from the two active states.
_ALLOWED: dict[AssignmentStatus, set[AssignmentStatus]] = {
    AssignmentStatus.ASSIGNED: {
        AssignmentStatus.OPENED,
        AssignmentStatus.SUBMITTED,
        AssignmentStatus.CANCELLED,
    },
    AssignmentStatus.OPENED: {AssignmentStatus.SUBMITTED, AssignmentStatus.CANCELLED},
    AssignmentStatus.SUBMITTED: set(),
    AssignmentStatus.CANCELLED: set(),
}


@dataclass
class Assignment:
    id: UUID
    campaign_id: UUID
    content_id: UUID
    assessor_id: UUID
    status: AssignmentStatus = AssignmentStatus.ASSIGNED
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AssignmentStatus):
            self.status = AssignmentStatus(self.status)

    @property
    def is_active(self) -> bool:
        """Active = not cancelled. Only active assignments occupy the uniqueness slot."""
        return self.status is not AssignmentStatus.CANCELLED

    @property
    def is_pending(self) -> bool:
        return self.status in (AssignmentStatus.ASSIGNED, AssignmentStatus.OPENED)

    def _transition(self, target: AssignmentStatus) -> None:
        if target not in _ALLOWED[self.status]:
            raise InvalidAssignmentTransition(f"cannot go from '{self.status}' to '{target}'")
        self.status = target
        self.updated_at = datetime.now(UTC)

    def open(self) -> None:
        """Idempotent: opening an already opened assignment is a no-op."""
        if self.status is AssignmentStatus.OPENED:
            return
        self._transition(AssignmentStatus.OPENED)

    def mark_submitted(self) -> None:
        """Driven by the completion policy on `EvaluationSubmitted`, never by a command.

        Idempotent, so replaying the event is safe (ADR-0003).
        """
        if self.status is AssignmentStatus.SUBMITTED:
            return
        self._transition(AssignmentStatus.SUBMITTED)

    def cancel(self) -> None:
        """Only cancellable while not submitted (ADR-0002)."""
        if self.status is AssignmentStatus.CANCELLED:
            return
        self._transition(AssignmentStatus.CANCELLED)
