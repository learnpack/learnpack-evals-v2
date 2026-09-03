"""What a campaign's human answers ARE — the one definition, shared by its readers.

ADR-0060 §1 fixes it: an evaluation belongs to a campaign when a non-cancelled assignment
`(campaign, content, assessor)` exists and the evaluation's `instrumentVersion` equals the
campaign's. And it says why this module exists rather than the rule being written twice —
*"a second definition of this campaign's evaluations — which would drift — never exists"*.

Two readers need it now: the campaign report (ADR-0060) and the validity of a claim against
that campaign (ADR-0063). They ask different questions of the same answers, which is exactly
the case where a shared scope pays and a shared *report* would not.

In `infrastructure` for the reason `reports.py` gives: consuming another module's published
contract is an outbound concern, which keeps `reporting/application` free of any dependency
on other modules.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.public import EvaluationDTO, EvaluationQueries
from app.modules.evaluation_design.public import RubricQueries, RubricSnapshot
from app.modules.orchestration.public import CampaignSummaryDTO, OrchestrationQueries
from app.modules.reporting.application import aggregation


class InstrumentUnavailable(Exception):
    """The campaign pins a reference instrument the store cannot resolve.

    Not a 404 about the campaign: the campaign exists and its pin is exactly what ADR-0056
    fixed at open. Reporting cannot say what the items were, and saying so is better than
    composing a report of quality ids with no questions attached.
    """


@dataclass(frozen=True)
class CampaignAnswers:
    """One campaign's human side, scoped and collapsed, before anybody interprets it."""

    campaign: CampaignSummaryDTO
    rubric: RubricSnapshot
    # Who the campaign ASKED, which is not who answered: an assessor with an open assignment
    # and no submission is still one of this campaign's assessors.
    asked_of: frozenset[tuple[UUID, UUID]]
    # Every evaluation the campaign asked for, by content — superseded ones included, because
    # a reader that reports what was corrected needs to see both.
    submitted: dict[UUID, list[EvaluationDTO]]
    # The same, with repetitions collapsed to the latest per assessor (ADR-0005/0006): a human
    # re-evaluation is a correction that supersedes. Every number is read off THIS one.
    counted: dict[UUID, list[EvaluationDTO]]


def campaign_answers(
    campaign_id: UUID,
    orchestration: OrchestrationQueries,
    evaluations: EvaluationQueries,
    rubrics: RubricQueries,
) -> CampaignAnswers | None:
    """`None` when no such campaign.

    Raises `InstrumentUnavailable` when the campaign resolves and its pin does not: the two
    are different failures and only the first is a 404 about the campaign.
    """
    campaign = orchestration.get_campaign(campaign_id)
    if campaign is None:
        return None

    rubric = rubrics.get_rubric(campaign.instrument_version_id)
    if rubric is None:
        raise InstrumentUnavailable(campaign.instrument_version_id)

    # ADR-0060 §1: what belongs to this campaign is what its assignments asked for. A
    # cancelled assignment asked for nothing, and an automated assessor never has one — which
    # is why no filter on assessor kind appears anywhere below.
    asked_of = {
        (assignment.content_id, assignment.assessor_id)
        for assignment in orchestration.list_assignments_for_campaign(campaign_id)
        if not assignment.is_cancelled
    }

    submitted: dict[UUID, list[EvaluationDTO]] = {cid: [] for cid in campaign.content_ids}
    for evaluation in evaluations.list_for_contents(campaign.content_ids):
        # The pin is read, not assumed: a course in two campaigns judged against two versions
        # answers two different sets of questions (ADR-0056).
        if evaluation.instrument_version_id != campaign.instrument_version_id:
            continue
        if (evaluation.content_id, evaluation.assessor_id) not in asked_of:
            continue
        submitted.setdefault(evaluation.content_id, []).append(evaluation)

    return CampaignAnswers(
        campaign=campaign,
        rubric=rubric,
        asked_of=frozenset(asked_of),
        submitted=submitted,
        counted={
            content_id: aggregation.collapse_latest_per_assessor(found)
            for content_id, found in submitted.items()
        },
    )
