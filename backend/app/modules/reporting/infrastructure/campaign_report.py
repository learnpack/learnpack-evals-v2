"""The campaign report's read side — one campaign, read at the grain of the item (ADR-0060).

Composes five modules through their `public.py` and aggregates in Python (ADR-0006): the
campaign and its assignments from Orchestration, the answers from Evaluation, the items from
Evaluation Design, the course names from Evaluand Registry and the assessors' names from
Identity. No cross-module JOIN, no read-model table, and reads batched so the cost does not
follow the size of the scope.

In `infrastructure` for the reason `reports.py` gives: consuming another module's published
contract is an outbound concern, which is what keeps `reporting/application` free of any
dependency on other modules — and what the architecture test enforces.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.modules.evaluation.public import EvaluationDTO, EvaluationQueries
from app.modules.evaluation_design.public import RubricQueries
from app.modules.identity.public import IdentityQueries
from app.modules.orchestration.public import OrchestrationQueries
from app.modules.reporting.application import aggregation, campaign_report
from app.modules.reporting.application.campaign_report import (
    ContentDisagreement,
    ContentItemAnswers,
    ItemSummary,
)

# --------------------------------------------------------------------------- DTOs


@dataclass(frozen=True)
class InstrumentDTO:
    """The reference instrument this campaign pinned (ADR-0056), named rather than hashed."""

    instrument_version_id: str
    name: str
    version: str
    response_format: str
    scale_min: int
    scale_max: int


@dataclass(frozen=True)
class QuorumDTO:
    contents_in_scope: int
    contents_complete: int
    coverage: float
    required_per_content: int
    # Distinct (content, assessor) submissions this campaign counts — superseded repetitions
    # excluded, because a correction is not a second evaluation (ADR-0005).
    evaluations_counted: int
    evaluations_expected: int
    superseded_count: int
    assessor_count: int


@dataclass(frozen=True)
class ItemReportDTO:
    quality_id: str
    order: int
    dimension: str
    # The statement the assessor agreed or disagreed with. Carried because an id is not a
    # question, and every screen reading this report has to show what was asked.
    prompt: str
    # What the course must declare for the item to be put to anybody (ADR-0053) — the reason
    # a `withheld_contents` count is not a defect.
    required_data: list[str]
    summary: ItemSummary


@dataclass(frozen=True)
class ScoreDetailDTO:
    quality_id: str
    score: int | None
    comment: str | None
    derived: bool


@dataclass(frozen=True)
class EvaluationDetailDTO:
    evaluation_id: UUID
    assessor_id: UUID
    assessor_name: str | None
    submitted_at: datetime | None
    superseded: bool
    scores: list[ScoreDetailDTO]


@dataclass(frozen=True)
class ContentReportDTO:
    content_id: UUID
    external_id: str
    # What the package calls itself (ADR-0059). Null when it declared none.
    title: str | None
    submitted_count: int
    required: int
    completed: bool
    disagreement: ContentDisagreement
    evaluations: list[EvaluationDetailDTO]


@dataclass(frozen=True)
class CampaignReportDTO:
    campaign_id: UUID
    name: str
    description: str | None
    status: str
    dataset_version_id: UUID | None
    instrument: InstrumentDTO
    quorum: QuorumDTO
    items: list[ItemReportDTO]
    contents: list[ContentReportDTO]


class InstrumentUnavailable(Exception):
    """The campaign pins a reference instrument the store cannot resolve.

    Not a 404 about the campaign: the campaign exists and its pin is exactly what ADR-0056
    fixed at open. Reporting cannot say what the items were, and saying so is better than
    composing a report of quality ids with no questions attached.
    """


# --------------------------------------------------------------------------- builder


def build_campaign_report(
    campaign_id: UUID,
    orchestration: OrchestrationQueries,
    evaluations: EvaluationQueries,
    contents: EvaluandRegistryQueries,
    identity: IdentityQueries,
    rubrics: RubricQueries,
) -> CampaignReportDTO | None:
    campaign = orchestration.get_campaign(campaign_id)
    if campaign is None:
        return None

    rubric = rubrics.get_rubric(campaign.instrument_version_id)
    if rubric is None:
        raise InstrumentUnavailable(campaign.instrument_version_id)

    progress = orchestration.get_campaign_progress(campaign_id)
    assert progress is not None  # the campaign resolved one line above

    # ADR-0060 §1: what belongs to this campaign is what its assignments asked for. A
    # cancelled assignment asked for nothing, and an automated assessor never has one — which
    # is why no filter on assessor kind appears anywhere below.
    asked_of = {
        (assignment.content_id, assignment.assessor_id)
        for assignment in orchestration.list_assignments_for_campaign(campaign_id)
        if not assignment.is_cancelled
    }
    campaign_assessors = {assessor_id for _, assessor_id in asked_of}

    mine = [
        evaluation
        for evaluation in evaluations.list_for_contents(campaign.content_ids)
        # The pin is read, not assumed: a course in two campaigns judged against two versions
        # answers two different sets of questions (ADR-0056).
        if evaluation.instrument_version_id == campaign.instrument_version_id
        and (evaluation.content_id, evaluation.assessor_id) in asked_of
    ]

    by_content: dict[UUID, list[EvaluationDTO]] = {cid: [] for cid in campaign.content_ids}
    for evaluation in mine:
        by_content.setdefault(evaluation.content_id, []).append(evaluation)

    # Repetitions are corrections: only the latest per assessor counts (ADR-0005/0006).
    counted = {
        content_id: aggregation.collapse_latest_per_assessor(found)
        for content_id, found in by_content.items()
    }

    names = identity.list_assessors(list({e.assessor_id for e in mine}))
    snapshots = {s.content_id: s for s in contents.list_content_snapshots()}
    progress_of = {c.content_id: c for c in progress.contents}

    items = [
        ItemReportDTO(
            quality_id=item.quality_id,
            order=item.order,
            dimension=item.dimension,
            prompt=item.prompt,
            required_data=list(item.required_data),
            summary=campaign_report.summarise_item(
                [
                    _answers_for(counted[content_id], item.quality_id)
                    for content_id in campaign.content_ids
                ],
                rubric.scale_min,
                rubric.scale_max,
            ),
        )
        # Every item of the pinned version, in its own order — including one nobody answered
        # (ADR-0060 §3).
        for item in sorted(rubric.items, key=lambda i: i.order)
    ]

    content_reports = []
    superseded_total = 0
    for content_id in campaign.content_ids:
        found = by_content.get(content_id, [])
        counted_ids = {e.evaluation_id for e in counted[content_id]}
        superseded_total += len(found) - len(counted_ids)
        snapshot = snapshots.get(content_id)
        row = progress_of.get(content_id)
        content_reports.append(
            ContentReportDTO(
                content_id=content_id,
                external_id=snapshot.external_id if snapshot else "",
                title=snapshot.title if snapshot else None,
                submitted_count=row.submitted_count if row else 0,
                required=row.required if row else campaign.required_evaluations_per_content,
                completed=row.completed if row else False,
                disagreement=campaign_report.content_disagreement(
                    [
                        _answers_for(counted[content_id], item.quality_id).scores
                        for item in rubric.items
                    ]
                ),
                evaluations=[
                    EvaluationDetailDTO(
                        evaluation_id=e.evaluation_id,
                        assessor_id=e.assessor_id,
                        assessor_name=_name_of(names, e.assessor_id),
                        submitted_at=e.submitted_at,
                        # Kept visible, and excluded from every number above it.
                        superseded=e.evaluation_id not in counted_ids,
                        scores=[
                            ScoreDetailDTO(
                                quality_id=s.quality_id,
                                score=s.score,
                                comment=s.comment,
                                derived=s.derived,
                            )
                            for s in e.scores
                        ],
                    )
                    for e in found
                ],
            )
        )

    return CampaignReportDTO(
        campaign_id=campaign.campaign_id,
        name=campaign.name,
        description=campaign.description,
        status=campaign.status,
        dataset_version_id=campaign.dataset_version_id,
        instrument=InstrumentDTO(
            instrument_version_id=rubric.rubric_version_id,
            name=rubric.name,
            version=rubric.version,
            response_format=rubric.response_format,
            scale_min=rubric.scale_min,
            scale_max=rubric.scale_max,
        ),
        quorum=QuorumDTO(
            contents_in_scope=len(campaign.content_ids),
            contents_complete=progress.completed_contents,
            coverage=progress.coverage,
            required_per_content=campaign.required_evaluations_per_content,
            evaluations_counted=sum(len(v) for v in counted.values()),
            evaluations_expected=len(campaign.content_ids)
            * campaign.required_evaluations_per_content,
            superseded_count=superseded_total,
            assessor_count=len(campaign_assessors),
        ),
        items=items,
        contents=content_reports,
    )


def _answers_for(evaluations: list[EvaluationDTO], quality_id: str) -> ContentItemAnswers:
    """One course's answers to one item — the three states kept apart (ADR-0060 §4).

    `withheld` needs at least one row to be true: a course nobody has evaluated yet has no
    rows at all, and reading that as *not asked* would report a campaign's own incompleteness
    as a generator's omission.
    """
    scores: list[int] = []
    abstentions = 0
    rows = 0
    derived_rows = 0
    for evaluation in evaluations:
        for score in evaluation.scores:
            if score.quality_id != quality_id:
                continue
            rows += 1
            if score.derived:
                derived_rows += 1
            elif score.score is None:
                abstentions += 1
            else:
                scores.append(score.score)
    return ContentItemAnswers(
        scores=tuple(scores),
        abstentions=abstentions,
        withheld=rows > 0 and rows == derived_rows,
    )


def _name_of(names: dict, assessor_id: UUID) -> str | None:
    dto = names.get(assessor_id)
    return None if dto is None else (dto.display_name or dto.email)
