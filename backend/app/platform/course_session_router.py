"""The course session an evaluator's page needs (ADR-0061).

It lives in the composition root, not in Orchestration's router, because it spans three
modules: Orchestration says whose assignment this is, Evaluand Registry says where the course
is deployed, and Course Session mints the credential that turns the embedded course from
readable into usable. Wiring three modules' adapters in one request is what a composition
root is for, and `platform/` is one — the same standing `ratification_router.py` has.

The route belongs to the assignment resource all the same; only the file sits outside the
module.

**Its own endpoint rather than a field on the assignment.** A session is minted, short-lived
and specific to one person, while the assignment detail is a description that any refetch may
serve from cache. Putting the token in that payload would spread a credential through every
cache that ever held an assignment, and mint one on every screen that reads it — including
the ones that never open the course.

**It answers 200 with no token rather than 5xx.** The course is readable without its AI, so a
provider outage degrades the page instead of replacing it. `reason` is what the screen shows
and what an operator acts on, so it carries the provider's own sentence.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.modules.course_session.application.ensure_seat import EnsureCourseSeat
from app.modules.course_session.application.mint_session import (
    MintCourseSession,
    MintCourseSessionCommand,
)
from app.modules.course_session.infrastructure.providers import get_seat_provider
from app.modules.course_session.infrastructure.repository import SqlAlchemyCourseSeatRepository
from app.modules.evaluand_registry.public import (
    EvaluandRegistryQueries,
    get_evaluand_registry_queries,
)
from app.modules.orchestration.public import OrchestrationQueries, get_orchestration_queries
from app.platform.security import CurrentAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(tags=["course-session"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]
Assignments = Annotated[OrchestrationQueries, Depends(get_orchestration_queries)]
Contents = Annotated[EvaluandRegistryQueries, Depends(get_evaluand_registry_queries)]

# What the embedded course reads the session from. The course platform consumes it on load
# and clears it from the address bar, which is why the token may travel here at all.
SESSION_QUERY_PARAM = "token"


class CourseSessionResponse(BaseModel):
    """Everything the evaluator's page needs to embed the course, session included."""

    # Null when the course has no deployed instance (ADR-0028) — a different thing from
    # having no session, and the page says so differently.
    url: str | None
    # False means: this loads, and the AI inside it will refuse. Never a reason to hide the
    # course.
    ai_session: bool
    reason: str | None


@router.get("/assignments/{assignment_id}/course-session", response_model=CourseSessionResponse)
def course_session(
    assignment_id: UUID,
    assessor: CurrentAssessor,
    assignments: Assignments,
    contents: Contents,
    uow: Uow,
) -> CourseSessionResponse:
    assignment = assignments.get_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignment not found")
    if assignment.assessor_id != assessor.assessor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your assignment")

    snapshot = contents.get_content_snapshot(assignment.content_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")

    if snapshot.consumable_url is None:
        # Nothing to embed, so nothing to mint a session for: minting one anyway would spend
        # a provisioning round trip on a page that will show "no deployed instance".
        return CourseSessionResponse(url=None, ai_session=False, reason=None)

    settings = get_settings()
    provider = get_seat_provider()
    mint = MintCourseSession(
        ensure_seat=EnsureCourseSeat(
            seats=SqlAlchemyCourseSeatRepository(uow.session),
            provider=provider,
            publisher=uow.events,
            uow=uow,
            email_template=settings.seat_email_template,
        ),
        provider=provider,
    )
    session = mint(MintCourseSessionCommand(assessor_id=assessor.assessor_id))

    return CourseSessionResponse(
        url=_with_session(snapshot.consumable_url, session.token),
        ai_session=session.granted,
        reason=session.reason,
    )


def _with_session(url: str, token: str | None) -> str:
    """Append the session to the course's own URL, preserving whatever it already carries.

    Hand-built rather than parsed and re-encoded: the stored URL is what an operator
    declared and what the course platform serves, and a round trip through a query parser
    can reorder or re-escape it into something subtly different.
    """
    if token is None:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{SESSION_QUERY_PARAM}={token}"
