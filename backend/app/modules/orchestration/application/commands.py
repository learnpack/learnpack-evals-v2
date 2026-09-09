"""Orchestration use cases (08-code.md §5).

Each writes its aggregate and publishes its event through the same `UnitOfWork`, so the
outbox row commits atomically with the state change (ADR-0003).
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.orchestration.application.ports import (
    AssessorsGatewayPort,
    AssignmentRepositoryPort,
    CampaignRepositoryPort,
    DatasetsGatewayPort,
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


class AssessorNotFound(Exception):
    """The assignment names somebody this store cannot resolve (ADR-0067 §2).

    `assessors` belongs to another module, so no foreign key says it — the same hole
    `UnknownDatasetVersion` fills for the scope, filled the same way.
    """


class AssessorCannotBeAsked(Exception):
    """Somebody exists behind the id, and a course still cannot be given to them (ADR-0067).

    One refusal for both reasons, because they are one fact from the campaign's side: there
    will be no answer. The message says which, since that is what the console shows and the
    two are undone differently — an automated assessor is run by a study instead, a
    deactivated person is reactivated or replaced.
    """


class UnknownDatasetVersion(Exception):
    """The campaign names a dataset version this store cannot resolve (ADR-0058 §5).

    There is no foreign key to say it — `dataset_versions` belongs to another module — so this
    is the gate, and it runs before anything is written.
    """


@dataclass(frozen=True)
class OpenCampaignCommand:
    name: str
    instrument_version_id: str
    required_evaluations_per_content: int
    dataset_version_id: UUID
    description: str | None = None
    golden_coverage_threshold: float = 1.0


class OpenCampaign:
    """Creates the campaign already open (MVP exposes no draft step).

    The scope is **not** passed in: it is read off the dataset version the campaign names, and
    copied (ADR-0058 §5). The copy is what the assignment path reads and what makes the scope
    survive whatever happens to the set afterwards; the version records how it was chosen.
    """

    def __init__(
        self,
        campaigns: CampaignRepositoryPort,
        datasets: DatasetsGatewayPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._datasets = datasets
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: OpenCampaignCommand) -> EvaluationCampaign:
        content_ids = self._datasets.get_version_members(command.dataset_version_id)
        if content_ids is None:
            raise UnknownDatasetVersion(str(command.dataset_version_id))

        campaign = EvaluationCampaign(
            id=new_id(),
            name=command.name,
            description=command.description,
            instrument_version_id=command.instrument_version_id,
            required_evaluations_per_content=command.required_evaluations_per_content,
            dataset_version_id=command.dataset_version_id,
            content_ids=list(content_ids),
            golden_coverage_threshold=command.golden_coverage_threshold,
        )
        campaign.open()

        self._campaigns.add(campaign)
        self._publisher.publish(events.campaign_opened(campaign))
        self._uow.commit()
        return campaign


@dataclass(frozen=True)
class RenameCampaignCommand:
    campaign_id: UUID
    name: str
    description: str | None = None


class RenameCampaign:
    """Replaces the label whole, in any status — a name binds nothing (ADR-0055)."""

    def __init__(
        self,
        campaigns: CampaignRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RenameCampaignCommand) -> EvaluationCampaign:
        campaign = self._campaigns.get(command.campaign_id)
        if campaign is None:
            raise CampaignNotFound(str(command.campaign_id))

        campaign.rename(command.name, command.description)  # raises InvalidCampaign if blank
        self._campaigns.update_label(campaign)
        self._publisher.publish(events.campaign_renamed(campaign))
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
        assessors: AssessorsGatewayPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._campaigns = campaigns
        self._assignments = assignments
        self._assessors = assessors
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: AssignContentCommand) -> Assignment:
        campaign = self._campaigns.get(command.campaign_id)
        if campaign is None:
            raise CampaignNotFound(str(command.campaign_id))
        campaign.ensure_accepts_assignments()
        if not campaign.includes(command.content_id):
            raise ContentNotInCampaign(str(command.content_id))

        # Before anything is written, and before the duplicate lookup: whether there is
        # somebody there to read the course is a question about the act itself, and an
        # assignment nobody can answer is worse than none (ADR-0067).
        assessee = self._assessors.get_assessee(command.assessor_id)
        if assessee is None:
            raise AssessorNotFound(str(command.assessor_id))
        if not assessee.is_human:
            raise AssessorCannotBeAsked(
                "an automated assessor is run against an instrument, never assigned a course"
            )
        if not assessee.is_active:
            raise AssessorCannotBeAsked("a deactivated assessor takes no new work")

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
    "AssessorCannotBeAsked",
    "AssessorNotFound",
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
    "RenameCampaign",
    "RenameCampaignCommand",
]
