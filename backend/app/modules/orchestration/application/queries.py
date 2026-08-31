"""Read-only query port of Orchestration (05-connect.md).

`get_assignment` is how Evaluation resolves `assignmentId → (content, instrumentVersion)` without
touching orchestration's tables or domain.
"""

from uuid import UUID

from app.modules.orchestration.application.dtos import (
    AssignmentDTO,
    CampaignProgressDTO,
    CampaignSummaryDTO,
    ContentProgressDTO,
)
from app.modules.orchestration.application.ports import (
    AssignmentRepositoryPort,
    CampaignRepositoryPort,
)
from app.modules.orchestration.domain.assignment import Assignment
from app.modules.orchestration.domain.campaign import EvaluationCampaign


def _to_dto(assignment: Assignment, campaign: EvaluationCampaign) -> AssignmentDTO:
    return AssignmentDTO(
        assignment_id=assignment.id,
        campaign_id=assignment.campaign_id,
        content_id=assignment.content_id,
        assessor_id=assignment.assessor_id,
        status=str(assignment.status),
        instrument_version_id=campaign.instrument_version_id,
    )


def get_assignment(
    assignments: AssignmentRepositoryPort,
    campaigns: CampaignRepositoryPort,
    assignment_id: UUID,
) -> AssignmentDTO | None:
    assignment = assignments.get(assignment_id)
    if assignment is None:
        return None
    campaign = campaigns.get(assignment.campaign_id)
    if campaign is None:
        return None
    return _to_dto(assignment, campaign)


def get_pending_assignments(
    assignments: AssignmentRepositoryPort,
    campaigns: CampaignRepositoryPort,
    assessor_id: UUID,
) -> list[AssignmentDTO]:
    """The evaluator's to-do list: assignments in `assigned` or `opened`."""
    result = []
    for assignment in assignments.list_pending_for_assessor(assessor_id):
        campaign = campaigns.get(assignment.campaign_id)
        if campaign is not None:
            result.append(_to_dto(assignment, campaign))
    return result


def get_campaign_progress(
    assignments: AssignmentRepositoryPort,
    campaigns: CampaignRepositoryPort,
    campaign_id: UUID,
) -> CampaignProgressDTO | None:
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        return None

    # One count for the whole scope: asking per content is one query per course, which forty
    # courses feel and a demo campaign never did.
    submitted_by_content = assignments.count_submitted_by_content(campaign_id)
    contents = []
    for content_id in campaign.content_ids:
        submitted = submitted_by_content.get(content_id, 0)
        contents.append(
            ContentProgressDTO(
                content_id=content_id,
                submitted_count=submitted,
                required=campaign.required_evaluations_per_content,
                completed=campaign.is_complete_with(submitted),
            )
        )

    return CampaignProgressDTO(
        campaign_id=campaign.id,
        instrument_version_id=campaign.instrument_version_id,
        status=str(campaign.status),
        required_evaluations_per_content=campaign.required_evaluations_per_content,
        contents=contents,
        golden_coverage_threshold=campaign.golden_coverage_threshold,
    )


def list_assignments(
    assignments: AssignmentRepositoryPort, campaigns: CampaignRepositoryPort
) -> list[AssignmentDTO]:
    """Every assignment across every campaign — the input of the admin progress report."""
    result = []
    for campaign in campaigns.list_all():
        for assignment in assignments.list_for_campaign(campaign.id):
            result.append(_to_dto(assignment, campaign))
    return result


def list_assignments_for_campaign(
    assignments: AssignmentRepositoryPort,
    campaigns: CampaignRepositoryPort,
    campaign_id: UUID,
) -> list[AssignmentDTO]:
    """One campaign's assignments, cancelled ones included.

    Whoever asks decides what to do with a cancellation: the campaign report needs the
    cancelled rows *out* (ADR-0060 §1) and the console's assignment table needs them *in*.
    Filtering here would serve one of them and hide the other's data.
    """
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        return []
    return [
        _to_dto(assignment, campaign) for assignment in assignments.list_for_campaign(campaign_id)
    ]


def get_campaign(campaigns: CampaignRepositoryPort, campaign_id: UUID) -> CampaignSummaryDTO | None:
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        return None
    return CampaignSummaryDTO(
        campaign_id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        status=str(campaign.status),
        instrument_version_id=campaign.instrument_version_id,
        required_evaluations_per_content=campaign.required_evaluations_per_content,
        dataset_version_id=campaign.dataset_version_id,
        content_ids=list(campaign.content_ids),
    )
