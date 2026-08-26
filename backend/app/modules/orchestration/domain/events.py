"""Domain events published by Evaluation Orchestration (02-discover.md, phases 3–4)."""

from uuid import UUID

from app.modules.orchestration.domain.assignment import Assignment
from app.modules.orchestration.domain.campaign import EvaluationCampaign
from app.shared.domain.events import DomainEvent

CAMPAIGN_AGGREGATE = "EvaluationCampaign"
ASSIGNMENT_AGGREGATE = "Assignment"


def campaign_opened(campaign: EvaluationCampaign) -> DomainEvent:
    """The human realisation of `EvaluationRunStarted` — pivotal."""
    return DomainEvent(
        event_type="CampaignOpened",
        aggregate_type=CAMPAIGN_AGGREGATE,
        aggregate_id=str(campaign.id),
        payload={
            "campaignId": str(campaign.id),
            "name": campaign.name,
            "description": campaign.description,
            "instrumentVersionId": campaign.instrument_version_id,
            "requiredEvaluationsPerContent": campaign.required_evaluations_per_content,
            "contentIds": [str(c) for c in campaign.content_ids],
        },
    )


def campaign_renamed(campaign: EvaluationCampaign) -> DomainEvent:
    """The label, replaced whole (ADR-0055). No policy reacts to it; `CampaignClosed` has no
    reader either, and inside Orchestration every state change of the aggregate is recorded."""
    return DomainEvent(
        event_type="CampaignRenamed",
        aggregate_type=CAMPAIGN_AGGREGATE,
        aggregate_id=str(campaign.id),
        payload={
            "campaignId": str(campaign.id),
            "name": campaign.name,
            "description": campaign.description,
        },
    )


def campaign_closed(campaign: EvaluationCampaign) -> DomainEvent:
    return DomainEvent(
        event_type="CampaignClosed",
        aggregate_type=CAMPAIGN_AGGREGATE,
        aggregate_id=str(campaign.id),
        payload={"campaignId": str(campaign.id)},
    )


def _assignment_event(event_type: str, assignment: Assignment) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_type=ASSIGNMENT_AGGREGATE,
        aggregate_id=str(assignment.id),
        payload={
            "assignmentId": str(assignment.id),
            "campaignId": str(assignment.campaign_id),
            "contentId": str(assignment.content_id),
            "assessorId": str(assignment.assessor_id),
        },
    )


def assignment_created(assignment: Assignment) -> DomainEvent:
    return _assignment_event("AssignmentCreated", assignment)


def assignment_opened(assignment: Assignment) -> DomainEvent:
    return _assignment_event("AssignmentOpened", assignment)


def assignment_cancelled(assignment: Assignment) -> DomainEvent:
    return _assignment_event("AssignmentCancelled", assignment)


def content_evaluation_completed(
    campaign_id: UUID, content_id: UUID, instrument_version_id: str, submitted_count: int
) -> DomainEvent:
    """Pivotal, and **relative to the campaign** — not a global fact about the content.

    Emitted by Orchestration (which knows the quorum), not by the Evaluation core
    (07-define.md, "Refinamiento vs Discover").
    """
    return DomainEvent(
        event_type="ContentEvaluationCompleted",
        aggregate_type=CAMPAIGN_AGGREGATE,
        aggregate_id=str(campaign_id),
        payload={
            "campaignId": str(campaign_id),
            "contentId": str(content_id),
            "instrumentVersionId": instrument_version_id,
            "submittedCount": submitted_count,
        },
    )
