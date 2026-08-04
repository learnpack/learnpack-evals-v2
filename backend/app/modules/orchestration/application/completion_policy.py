"""Completion policy: `EvaluationSubmitted` → `ContentEvaluationCompleted` (ADR-0002).

Quorum is a **completion threshold over submissions, not provisioning**. On each submission:

1. mark `submitted` every open assignment of `(assessor, content)` whose campaign uses the
   same `instrumentVersion` — so one evaluation can satisfy several campaigns that asked for it,
   and reassignments work by themselves;
2. for each affected campaign, if `COUNT(assignments submitted) >= required` → record the
   completion and publish `ContentEvaluationCompleted`.

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
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationSubmittedFact:
    """The bits of `EvaluationSubmitted` this policy needs (the Published Language)."""

    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str


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
        """Returns the campaigns that reached completion for this content."""
        open_assignments = self._assignments.list_open_for_assessor_and_content(
            fact.assessor_id, fact.content_id
        )

        affected_campaigns = []
        for assignment in open_assignments:
            campaign = self._campaigns.get(assignment.campaign_id)
            if campaign is None:
                continue
            # Only campaigns evaluating with the same rubric are satisfied by this evaluation.
            if campaign.instrument_version_id != fact.instrument_version_id:
                continue

            assignment.mark_submitted()
            self._assignments.save_status(assignment)
            affected_campaigns.append(campaign)

        completed: list[UUID] = []
        for campaign in affected_campaigns:
            submitted = self._assignments.count_submitted(campaign.id, fact.content_id)
            if not campaign.is_complete_with(submitted):
                continue
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
                completed.append(campaign.id)

        self._uow.commit()
        if completed:
            logger.info("content %s completed in campaigns %s", fact.content_id, completed)
        return completed
