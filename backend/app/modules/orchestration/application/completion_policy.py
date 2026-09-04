"""Completion policy: `EvaluationSubmitted` → `ContentEvaluationCompleted` (ADR-0002).

Quorum is a **completion threshold over submissions, not provisioning**. On each submission:

1. mark `submitted` **the assignment that was answered**, and no other (ADR-0065). An answer
   given to one round is not a delivery to another, and a campaign that claimed one was
   reporting work it never received;
2. if `COUNT(assignments submitted) >= required` for its campaign → record the completion and
   publish `ContentEvaluationCompleted`.

Counting `assignments submitted` is equivalent to counting distinct assessors because at most
one active assignment exists per `(campaign, content, assessor)` — the partial unique index
`uq_assignments_active`.

Consistency is **eventual**: this runs after the evaluation's transaction committed, in its
own transaction. It is also **idempotent**, so a replay from the `events` table is safe
(ADR-0003).
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.modules.orchestration.application.ports import (
    AssignmentRepositoryPort,
    CampaignRepositoryPort,
    CompletionRepositoryPort,
)
from app.modules.orchestration.domain import events
from app.modules.orchestration.domain.assignment import AssignmentStatus
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationSubmittedFact:
    """The bits of `EvaluationSubmitted` this policy needs (the Published Language)."""

    content_id: UUID
    # `None` for an automated evaluation, and for an event published before ADR-0065. Neither
    # answers an assignment, so neither advances one.
    assignment_id: UUID | None


class HandleEvaluationSubmitted:
    def __init__(
        self,
        campaigns: CampaignRepositoryPort,
        assignments: AssignmentRepositoryPort,
        completions: CompletionRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._assignments = assignments
        self._completions = completions
        self._publisher = publisher
        self._uow = uow

    def __call__(self, fact: EvaluationSubmittedFact) -> list[UUID]:
        """Returns the campaigns that reached completion for this content.

        At most one, because an evaluation answers at most one assignment and an assignment
        belongs to one campaign (ADR-0065). The list shape is kept because the caller and the
        log read it, and because nothing is gained by narrowing a return nobody indexes.
        """
        assignment = self._assignments.get(fact.assignment_id) if fact.assignment_id else None
        # No assignment means no round asked for this — an automated evaluation, or one from
        # before the answer was attributable. Nothing to advance, and inventing a campaign for
        # it is what this policy stopped doing.
        campaign = self._campaigns.get(assignment.campaign_id) if assignment is not None else None
        if assignment is None or campaign is None:
            self._uow.commit()
            return []
        if assignment.status is AssignmentStatus.CANCELLED:
            # Cancelling a submitted assignment is refused, so this is an answer to something
            # that was withdrawn before it arrived. It advances nothing.
            self._uow.commit()
            return []

        assignment.mark_submitted()
        self._assignments.save_status(assignment)

        submitted = self._assignments.count_submitted(campaign.id, fact.content_id)
        if not campaign.is_complete_with(submitted):
            self._uow.commit()
            return []

        # Publish only if we actually recorded it — replays must not re-emit the event.
        newly_recorded = self._completions.record_completion(
            campaign.id, fact.content_id, campaign.instrument_version_id
        )
        if newly_recorded:
            self._publisher.publish(
                events.content_evaluation_completed(
                    campaign.id, fact.content_id, campaign.instrument_version_id, submitted
                )
            )

        self._uow.commit()
        if newly_recorded:
            logger.info("content %s completed in campaign %s", fact.content_id, campaign.id)
        return [campaign.id] if newly_recorded else []
