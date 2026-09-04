"""What a campaign's human answers ARE — the one definition, shared by its readers.

ADR-0060 §1 fixed it as a set lookup over `(content, assessor)`, because an evaluation carried
no attribution. ADR-0065 gave it one, and the rule became a single clause: an evaluation belongs
to the campaign of **the assignment it answered**. The instrument-version check and the special
case that kept automated evaluations out both dissolve into it — an evaluation that answered no
assignment is in no campaign.

The reason this module exists is unchanged, and it is ADR-0060's own —
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


class InstrumentUnavailable(Exception):
    """The campaign pins a reference instrument the store cannot resolve.

    Not a 404 about the campaign: the campaign exists and its pin is exactly what ADR-0056
    fixed at open. Reporting cannot say what the items were, and saying so is better than
    composing a report of quality ids with no questions attached.
    """


@dataclass(frozen=True)
class CampaignAnswers:
    """One campaign's human side, scoped, before anybody interprets it."""

    campaign: CampaignSummaryDTO
    rubric: RubricSnapshot
    # Who the campaign ASKED, which is not who answered: an assessor with an open assignment
    # and no submission is still one of this campaign's assessors.
    asked_of: frozenset[tuple[UUID, UUID]]
    # The answers this campaign received, by content. One list, not two: an assessor answers a
    # course at most once per campaign — one active assignment per (campaign, content,
    # assessor), one submission per assignment — so there is nothing to collapse and no
    # superseded row to keep beside it (ADR-0065 §7).
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
    # ADR-0060 §1 realized through ADR-0065: what belongs to this campaign is what its own
    # assignments were answered with. A cancelled assignment asked for nothing, and an
    # automated assessor never has one — which is why no filter on assessor kind appears
    # anywhere below.
    live = [
        assignment
        for assignment in orchestration.list_assignments_for_campaign(campaign_id)
        if not assignment.is_cancelled
    ]
    asked_of = {(assignment.content_id, assignment.assessor_id) for assignment in live}
    mine = {assignment.assignment_id for assignment in live}

    counted: dict[UUID, list[EvaluationDTO]] = {cid: [] for cid in campaign.content_ids}
    for evaluation in evaluations.list_for_contents(campaign.content_ids):
        # One test, where three used to be. The pin ADR-0056 fixed travels with the
        # assignment, so a course in two campaigns judged against two versions separates here
        # for the same reason everything else does.
        if evaluation.assignment_id not in mine:
            continue
        counted.setdefault(evaluation.content_id, []).append(evaluation)

    return CampaignAnswers(
        campaign=campaign,
        rubric=rubric,
        asked_of=frozenset(asked_of),
        counted=counted,
    )
