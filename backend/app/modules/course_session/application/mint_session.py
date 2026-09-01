"""Mint the session an evaluator's course page needs, or say why there is none.

**This use case does not raise.** Every other act in the product fails loudly, and should:
a refused invitation or a rejected score is something the caller must handle. A missing
course session is different — the course itself is still readable, and turning a provider
outage into a 500 would replace a working page with an error one. So the failure is an
answer: no token, and a sentence naming what went wrong.

That sentence reaches a human, so it comes from the port's own exception rather than a
generic phrase. "SEAT_EMAIL_TEMPLATE must contain {slug}" is something an operator can act
on; "could not create session" is not.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.course_session.application.dtos import CourseSessionDTO
from app.modules.course_session.application.ensure_seat import (
    EnsureCourseSeat,
    EnsureCourseSeatCommand,
)
from app.modules.course_session.application.ports import (
    ExternalSeat,
    SeatProviderPort,
    SeatProvisioningFailed,
)


@dataclass(frozen=True)
class MintCourseSessionCommand:
    assessor_id: UUID


class MintCourseSession:
    def __init__(self, ensure_seat: EnsureCourseSeat, provider: SeatProviderPort) -> None:
        self._ensure_seat = ensure_seat
        self._provider = provider

    def __call__(self, command: MintCourseSessionCommand) -> CourseSessionDTO:
        try:
            seat = self._ensure_seat(EnsureCourseSeatCommand(assessor_id=command.assessor_id))
            token = self._provider.mint_token(ExternalSeat.of(seat))
        except SeatProvisioningFailed as exc:
            return CourseSessionDTO(token=None, reason=str(exc))
        return CourseSessionDTO(token=token)
