"""`Assignment` and `EvaluationCampaign` invariants (ADR-0002) — pure domain, no DB."""

import pytest

from app.modules.orchestration.domain.assignment import (
    Assignment,
    AssignmentStatus,
    InvalidAssignmentTransition,
)
from app.modules.orchestration.domain.campaign import (
    CampaignStatus,
    EvaluationCampaign,
    InvalidCampaign,
)
from app.shared.domain.ids import new_id


def make_assignment(**overrides) -> Assignment:
    base = {
        "id": new_id(),
        "campaign_id": new_id(),
        "content_id": new_id(),
        "assessor_id": new_id(),
    }
    return Assignment(**(base | overrides))


def make_campaign(**overrides) -> EvaluationCampaign:
    base = {
        "id": new_id(),
        "rubric_version_id": "learnpack-pedagogical-v1",
        "required_evaluations_per_content": 2,
        "content_ids": [new_id()],
    }
    return EvaluationCampaign(**(base | overrides))


# --- Assignment lifecycle ---------------------------------------------------


def test_starts_assigned_and_pending():
    assignment = make_assignment()
    assert assignment.status is AssignmentStatus.ASSIGNED
    assert assignment.is_pending and assignment.is_active


def test_happy_path_assigned_opened_submitted():
    assignment = make_assignment()
    assignment.open()
    assert assignment.status is AssignmentStatus.OPENED
    assignment.mark_submitted()
    assert assignment.status is AssignmentStatus.SUBMITTED
    assert not assignment.is_pending


def test_can_submit_without_opening_first():
    assignment = make_assignment()
    assignment.mark_submitted()
    assert assignment.status is AssignmentStatus.SUBMITTED


def test_a_submitted_assignment_cannot_be_cancelled():
    """Only cancellable while not submitted (ADR-0002)."""
    assignment = make_assignment(status=AssignmentStatus.SUBMITTED)
    with pytest.raises(InvalidAssignmentTransition):
        assignment.cancel()


def test_a_cancelled_assignment_cannot_be_reopened_or_submitted():
    assignment = make_assignment(status=AssignmentStatus.CANCELLED)
    assert not assignment.is_active
    with pytest.raises(InvalidAssignmentTransition):
        assignment.open()
    with pytest.raises(InvalidAssignmentTransition):
        assignment.mark_submitted()


def test_open_and_mark_submitted_are_idempotent():
    """The policy may replay the same event (ADR-0003)."""
    assignment = make_assignment()
    assignment.open()
    assignment.open()
    assignment.mark_submitted()
    assignment.mark_submitted()
    assert assignment.status is AssignmentStatus.SUBMITTED


def test_cancel_is_idempotent():
    assignment = make_assignment()
    assignment.cancel()
    assignment.cancel()
    assert assignment.status is AssignmentStatus.CANCELLED


def test_status_accepts_the_raw_string_from_the_database():
    assert make_assignment(status="opened").status is AssignmentStatus.OPENED


# --- EvaluationCampaign -----------------------------------------------------


def test_campaign_starts_as_draft_and_opens():
    campaign = make_campaign()
    assert campaign.status is CampaignStatus.DRAFT
    campaign.open()
    assert campaign.status is CampaignStatus.OPEN


def test_cannot_open_with_an_empty_content_set():
    with pytest.raises(InvalidCampaign, match="empty content set"):
        make_campaign(content_ids=[]).open()


def test_required_evaluations_must_be_at_least_one():
    with pytest.raises(InvalidCampaign, match="at least 1"):
        make_campaign(required_evaluations_per_content=0)


def test_rubric_version_is_required():
    with pytest.raises(InvalidCampaign, match="rubric_version_id"):
        make_campaign(rubric_version_id="")


@pytest.mark.parametrize("threshold", [0, -0.5, 1.5])
def test_coverage_threshold_must_be_within_zero_and_one(threshold):
    with pytest.raises(InvalidCampaign, match="threshold"):
        make_campaign(golden_coverage_threshold=threshold)


def test_only_an_open_campaign_accepts_assignments():
    campaign = make_campaign()
    with pytest.raises(InvalidCampaign, match="not open"):
        campaign.ensure_accepts_assignments()
    campaign.open()
    campaign.ensure_accepts_assignments()


def test_closing_and_reopening():
    campaign = make_campaign()
    campaign.open()
    campaign.close()
    assert campaign.status is CampaignStatus.CLOSED
    with pytest.raises(InvalidCampaign, match="cannot be reopened"):
        campaign.open()


def test_only_an_open_campaign_can_be_closed():
    with pytest.raises(InvalidCampaign, match="only an open campaign"):
        make_campaign().close()


def test_quorum_rule():
    campaign = make_campaign(required_evaluations_per_content=2)
    assert not campaign.is_complete_with(1)
    assert campaign.is_complete_with(2)
    # Over-quorum is allowed (ADR-0002 open question, resolved: extras are kept).
    assert campaign.is_complete_with(3)


def test_empty_metadata_view_means_no_filtering():
    assert make_campaign(metadata_view=[]).metadata_view_or_none() is None
    assert make_campaign(metadata_view=["targetAudience"]).metadata_view_or_none() == [
        "targetAudience"
    ]
