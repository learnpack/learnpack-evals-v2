"""Orchestration use cases (08-code.md §5).

Each writes its aggregate and publishes its event through the same `UnitOfWork`, so the
outbox row commits atomically with the state change (ADR-0003).
"""

from dataclasses import dataclass, field
from uuid import UUID

from app.modules.orchestration.application.ports import (
    AssignmentRepositoryPort,
    CampaignRepositoryPort,
)
from app.modules.orchestration.domain import events
from app.modules.orchestration.domain.assignment import Assignment
from app.modules.orchestration.domain.campaign import EvaluationCampaign, InvalidCampaign
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class CampaignNotFound(Exception): ...


class AssignmentNotFound(Exception): ...


class DuplicateAssignment(Exception):
    """An active assignment already exists for (campaign, content, assessor) — ADR-0005."""


class ContentNotInCampaign(Exception): ...


@dataclass(frozen=True)
class OpenCampaignCommand:
    instrument_version_id: str
    required_evaluations_per_content: int
    content_ids: list[UUID]
    metadata_view: list[str] = field(default_factory=list)
    golden_coverage_threshold: float = 1.0


class OpenCampaign:
    """Creates the campaign already open (MVP exposes no draft step)."""

    def __init__(
        self,
        campaigns: CampaignRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: OpenCampaignCommand) -> EvaluationCampaign:
        campaign = EvaluationCampaign(
            id=new_id(),
            instrument_version_id=command.instrument_version_id,
            required_evaluations_per_content=command.required_evaluations_per_content,
            content_ids=list(command.content_ids),
            metadata_view=list(command.metadata_view),
            golden_coverage_threshold=command.golden_coverage_threshold,
        )
        campaign.open()

        self._campaigns.add(campaign)
        self._publisher.publish(events.campaign_opened(campaign))
        self._uow.commit()
        return campaign


@dataclass(frozen=True)
class AssignContentCommand:
    campaign_id: UUID
    content_id: UUID
    assessor_id: UUID


class AssignContent:
    def __init__(
        self,
        campaigns: CampaignRepositoryPort,
        assignments: AssignmentRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._assignments = assignments
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: AssignContentCommand) -> Assignment:
        campaign = self._campaigns.get(command.campaign_id)
        if campaign is None:
            raise CampaignNotFound(str(command.campaign_id))
        campaign.ensure_accepts_assignments()
        if not campaign.includes(command.content_id):
            raise ContentNotInCampaign(str(command.content_id))

        # At most one ACTIVE assignment per (campaign, content, assessor) — the DB partial
        # unique index is the backstop; this gives a clean 409.
        if self._assignments.find_active(
            command.campaign_id, command.content_id, command.assessor_id
        ):
            raise DuplicateAssignment(
                "this assessor already has an active assignment for that content"
            )

        assignment = Assignment(
            id=new_id(),
            campaign_id=command.campaign_id,
            content_id=command.content_id,
            assessor_id=command.assessor_id,
        )
        self._assignments.add(assignment)
        self._publisher.publish(events.assignment_created(assignment))
        self._uow.commit()
        return assignment


class OpenAssignment:
    def __init__(
        self,
        assignments: AssignmentRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._assignments = assignments
        self._publisher = publisher
        self._uow = uow

    def __call__(self, assignment_id: UUID) -> Assignment:
        assignment = self._assignments.get(assignment_id)
        if assignment is None:
            raise AssignmentNotFound(str(assignment_id))

        assignment.open()
        self._assignments.save_status(assignment)
        self._publisher.publish(events.assignment_opened(assignment))
        self._uow.commit()
        return assignment


class CancelAssignment:
    """Cancel (and, for a reassign, follow with a fresh `AssignContent`) — ADR-0002."""

    def __init__(
        self,
        assignments: AssignmentRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._assignments = assignments
        self._publisher = publisher
        self._uow = uow

    def __call__(self, assignment_id: UUID) -> Assignment:
        assignment = self._assignments.get(assignment_id)
        if assignment is None:
            raise AssignmentNotFound(str(assignment_id))

        # Raises InvalidAssignmentTransition if already submitted.
        assignment.cancel()
        self._assignments.save_status(assignment)
        self._publisher.publish(events.assignment_cancelled(assignment))
        self._uow.commit()
        return assignment


class CloseCampaign:
    def __init__(
        self,
        campaigns: CampaignRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._publisher = publisher
        self._uow = uow

    def __call__(self, campaign_id: UUID) -> EvaluationCampaign:
        campaign = self._campaigns.get(campaign_id)
        if campaign is None:
            raise CampaignNotFound(str(campaign_id))

        campaign.close()  # raises InvalidCampaign if not open
        self._campaigns.update_status(campaign)
        self._publisher.publish(events.campaign_closed(campaign))
        self._uow.commit()
        return campaign


__all__ = [
    "AssignContent",
    "AssignContentCommand",
    "AssignmentNotFound",
    "CampaignNotFound",
    "CancelAssignment",
    "CloseCampaign",
    "ContentNotInCampaign",
    "DuplicateAssignment",
    "InvalidCampaign",
    "OpenAssignment",
    "OpenCampaign",
    "OpenCampaignCommand",
]
