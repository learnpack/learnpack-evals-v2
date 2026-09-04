"""The validity of a claim against a campaign — the read side (ADR-0063).

Composes five modules through their `public.py` and computes in Python (ADR-0006): the
campaign's human answers through the shared scope, the automated judgments from Evaluation,
the claims from Evaluation Design, and the assessor's label from Identity. No cross-module
JOIN, no read-model table, nothing persisted (ADR-0063 §8).

Its coordinates are explicit and all three matter: a campaign fixes the human side entirely
(and therefore the version of the form), while the instrument version and the assessor fix
whose verdicts are being qualified. Nothing is inferred — a defaulted coordinate would let one
URL mean different things over time (ADR-0063 §7).
"""

import statistics
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.public import ContentSnapshot, EvaluandRegistryQueries
from app.modules.evaluation.public import (
    EvaluationDTO,
    EvaluationQueries,
    FindingDTO,
    JudgmentClaimDTO,
    QualityJudgmentDTO,
)
from app.modules.evaluation_design.public import InstrumentQueries, RubricQueries
from app.modules.identity.public import AssessorDTO, IdentityQueries
from app.modules.orchestration.public import OrchestrationQueries
from app.modules.reporting.application import claim_validity
from app.modules.reporting.application.claim_validity import (
    ACCEPT,
    GREY,
    REJECT,
    Confusion,
    HumanVerdict,
    Ratio,
    Thresholds,
)
from app.modules.reporting.infrastructure.campaign_scope import campaign_answers

# --------------------------------------------------------------------------- DTOs


@dataclass(frozen=True)
class HumanAnswerDTO:
    """One expert on one item of one course: the number, and what they wrote beside it.

    The comment is the half that says *why*, and it is the reason this reaches a reader at
    all — an expert's note is the critique that names what the judge missed. `rater` is not a
    word of this domain (GLOSSARY): the human side of a campaign is a human `Assessor`.
    """

    assessor_id: UUID
    assessor_name: str | None
    score: int
    comment: str | None


@dataclass(frozen=True)
class CitedFindingDTO:
    """What the assessor raised against a claim on one course, in its own words.

    The quote is absent only on an absence-derived fail, whose failure mode is mechanical
    (ADR-0021) — there was no passage to cite because the point is that nothing was there.
    """

    criterion_id: str
    failure_mode: str
    quote: str | None
    locator: dict[str, Any] | None


@dataclass(frozen=True)
class DiscordantCourseDTO:
    """One course where the two sides contradicted each other, with both sides quoted.

    This is what a `weak` claim is rewritten from, and it is deliberately not a verdict about
    the course (ADR-0063 §9): nothing here is corrected, reconciled or scored. It is the pair
    of readings, side by side, so that a reader can see which of the two is wrong.
    """

    content_id: UUID
    # The external id identifies and the title only describes (ADR-0059), so both travel: a
    # reader moving to another screen may meet this course under the other label.
    external_id: str
    title: str | None
    # Which corner of the 2x2 — `refuted_accepted` or `supported_rejected`.
    cell: str
    human_mean: float
    # Whether the experts landed on the same side HERE. `None` when only one of them answered.
    # Read this first: where it is false there was no human answer to match, and the suspect
    # is the reference item rather than the assessor.
    experts_agree: bool | None
    answers: list[HumanAnswerDTO]
    # {pass, fail, noEvidence, notApplicable, notAssessed} — how the claim reached its status.
    evidence_basis: dict[str, int]
    # Empty whenever the assessor said `supported`: it raised nothing, and that silence is the
    # finding. `evidence_basis` is what explains it.
    findings: list[CitedFindingDTO]


@dataclass(frozen=True)
class ClaimValidityDTO:
    """One claim, and how much it follows the panel."""

    claim_id: str
    statement: str
    quality_id: str
    dimension: str | None
    # The 2x2's size — courses where both sides committed. Every ratio below reads against it.
    sample: int
    sensitivity: Ratio
    specificity: Ratio
    # `None` rather than 0 wherever the table cannot support the number (ADR-0063 §3).
    kappa: float | None
    youden_j: float | None
    judge_agreement: float | None
    # The panel's agreement with itself on the same cut — the ceiling of everything above it.
    human_agreement: float | None
    # The three ways a course of the sample stayed out of the 2x2, counted apart because they
    # mean different things: the panel would not commit, nobody answered, the assessor abstained.
    grey: int
    unanswered: int
    insufficient: int
    status: str
    reason: str | None
    # The courses behind the numbers above that contradicted the assessor, widest disagreement
    # first. Empty when there is no sample, and empty when the two sides never clashed — which
    # for a claim with a sample is the good outcome, not a missing one.
    discordant: list[DiscordantCourseDTO]


@dataclass(frozen=True)
class ClaimValidityReportDTO:
    campaign_id: UUID
    campaign_name: str
    assessor_id: UUID
    assessor_name: str | None
    instrument_version_id: str
    instrument_name: str
    # Courses in the campaign's scope, and the ones this assessor also judged — the second is
    # the sample every row is computed over, derived on read and never stored (ADR-0058 §9).
    courses_in_campaign: int
    courses_judged: int
    claims: list[ClaimValidityDTO]


class AssessorUnknown(Exception):
    """No such assessor. Not a 404 about the campaign, which resolved."""


class InstrumentNotPublished(Exception):
    """The automated instrument version does not resolve."""


# --------------------------------------------------------------------------- builder


def build_claim_validity(
    campaign_id: UUID,
    assessor_id: UUID,
    instrument_version_id: str,
    orchestration: OrchestrationQueries,
    evaluations: EvaluationQueries,
    contents: EvaluandRegistryQueries,
    rubrics: RubricQueries,
    instruments: InstrumentQueries,
    identity: IdentityQueries,
    thresholds: Thresholds = claim_validity.DEFAULT_THRESHOLDS,
) -> ClaimValidityReportDTO | None:
    """`None` when no such campaign; raises when the other two coordinates do not resolve."""
    answers = campaign_answers(campaign_id, orchestration, evaluations, rubrics)
    if answers is None:
        return None

    instrument = instruments.get_instrument(instrument_version_id)
    if instrument is None:
        raise InstrumentNotPublished(instrument_version_id)

    campaign = answers.campaign
    elicited = {item.quality_id for item in answers.rubric.items}

    judgments = _latest_per_content(
        evaluations.get_judgments(campaign.content_ids, instrument_version_id, assessor_id)
    )
    # The sample: the campaign's courses this assessor also judged. Ordered so the numbers do
    # not depend on dictionary insertion.
    sample_ids = [cid for cid in campaign.content_ids if cid in judgments]

    # One lookup for every name on both sides of the comparison: the assessor being qualified,
    # and the experts whose answers qualify it.
    names = identity.list_assessors(
        list(
            {assessor_id}
            | {e.assessor_id for cid in sample_ids for e in answers.counted.get(cid, [])}
        )
    )
    if assessor_id not in names:
        raise AssessorUnknown(str(assessor_id))
    assessor = names[assessor_id]

    human = {
        cid: _human_side(answers.counted.get(cid, []), names, thresholds) for cid in sample_ids
    }
    machine = {cid: _claims_of(judgments[cid]) for cid in sample_ids}
    # Batched, never per course (ADR-0006). Findings exist only where something was raised, so
    # this is small: the courses the assessor refuted something on.
    raised = _findings_by_course_and_claim(
        evaluations.get_findings(sample_ids, instrument_version_id, assessor_id)
    )
    courses = {s.content_id: s for s in contents.list_content_snapshots()}

    claims = [
        _validity_of(
            claim_id=claim.claim_id,
            statement=claim.statement,
            # ADR-0026: exactly one, checked at publish. The list is the storage shape.
            quality_id=claim.quality_ids[0] if claim.quality_ids else "",
            dimension=instrument.quality_dimensions.get(
                claim.quality_ids[0] if claim.quality_ids else ""
            ),
            elicited=elicited,
            sample_ids=sample_ids,
            human=human,
            machine=machine,
            raised=raised,
            courses=courses,
            thresholds=thresholds,
        )
        # Every claim of the pinned version, including the ones with no human item: a reading
        # that showed only what has data could not be told apart from an instrument that never
        # asked the rest (ADR-0063 §6, ADR-0011 §3).
        for claim in instrument.claims
    ]

    return ClaimValidityReportDTO(
        campaign_id=campaign.campaign_id,
        campaign_name=campaign.name,
        assessor_id=assessor_id,
        assessor_name=assessor.display_name or assessor.email,
        instrument_version_id=instrument.instrument_version_id,
        instrument_name=instrument.name,
        courses_in_campaign=len(campaign.content_ids),
        courses_judged=len(sample_ids),
        claims=claims,
    )


# --------------------------------------------------------------------------- internals


def _latest_per_content(judgments: list[QualityJudgmentDTO]) -> dict[UUID, QualityJudgmentDTO]:
    """Judgments are append-only; the most recent per content is the current one."""
    latest: dict[UUID, QualityJudgmentDTO] = {}
    for judgment in sorted(judgments, key=lambda j: j.derived_at):
        latest[judgment.content_id] = judgment
    return latest


@dataclass(frozen=True)
class _HumanSide:
    """One course's human answers, already cut, by quality."""

    verdict: dict[str, HumanVerdict]
    # Each rater's own cut, which is what the ceiling is measured on (ADR-0063 §4).
    per_rater: dict[str, list[HumanVerdict]]
    # The same answers uncut, with who gave them and what they wrote. The cut is what the
    # numbers are computed on; this is what a reader has to see to know why they came out so.
    answers: dict[str, list[HumanAnswerDTO]]


def _human_side(
    evaluations: list[EvaluationDTO], names: dict[UUID, AssessorDTO], thresholds: Thresholds
) -> _HumanSide:
    scores: dict[str, list[int]] = {}
    answers: dict[str, list[HumanAnswerDTO]] = {}
    for evaluation in evaluations:
        for score in evaluation.scores:
            # An abstention and a derived row are not judgements (ADR-0052 §4, ADR-0053), so
            # neither reaches the cut.
            if score.score is None or score.derived:
                continue
            scores.setdefault(score.quality_id, []).append(score.score)
            answers.setdefault(score.quality_id, []).append(
                HumanAnswerDTO(
                    assessor_id=evaluation.assessor_id,
                    assessor_name=_name_of(names, evaluation.assessor_id),
                    score=score.score,
                    comment=score.comment,
                )
            )
    return _HumanSide(
        verdict={q: claim_validity.human_verdict(s, thresholds) for q, s in scores.items()},
        per_rater={q: claim_validity.rater_verdicts(s, thresholds) for q, s in scores.items()},
        answers=answers,
    )


def _name_of(names: dict[UUID, AssessorDTO], assessor_id: UUID) -> str | None:
    assessor = names.get(assessor_id)
    if assessor is None:
        return None
    return assessor.display_name or assessor.email


def _claims_of(judgment: QualityJudgmentDTO) -> dict[str, JudgmentClaimDTO]:
    """The whole claim row, not just its status: `evidence_basis` explains a silent verdict."""
    return {claim.claim_id: claim for claim in judgment.claims}


def _findings_by_course_and_claim(
    findings: list[FindingDTO],
) -> dict[tuple[UUID, str], list[CitedFindingDTO]]:
    """Findings are organised under the claim they compromise (GLOSSARY), one course at a time."""
    grouped: dict[tuple[UUID, str], list[CitedFindingDTO]] = {}
    for finding in findings:
        grouped.setdefault((finding.content_id, finding.claim_id), []).append(
            CitedFindingDTO(
                criterion_id=finding.criterion_id,
                failure_mode=finding.failure_mode,
                quote=finding.quote,
                locator=finding.locator,
            )
        )
    return grouped


def _validity_of(
    *,
    claim_id: str,
    statement: str,
    quality_id: str,
    dimension: str | None,
    elicited: set[str],
    sample_ids: list[UUID],
    human: dict[UUID, _HumanSide],
    machine: dict[UUID, dict[str, JudgmentClaimDTO]],
    raised: dict[tuple[UUID, str], list[CitedFindingDTO]],
    courses: dict[UUID, ContentSnapshot],
    thresholds: Thresholds,
) -> ClaimValidityDTO:
    if quality_id not in elicited:
        # The reference instrument does not ask about this quality, so there is no human
        # column to compare against — and no campaign fixes that.
        return _empty(claim_id, statement, quality_id, dimension, "no_reference_item")

    pairs: list[tuple[HumanVerdict, str]] = []
    per_rater: list[list[HumanVerdict]] = []
    discordant: list[tuple[float, DiscordantCourseDTO]] = []
    grey = unanswered = insufficient = 0

    for content_id in sample_ids:
        side = human[content_id]
        verdict = side.verdict.get(quality_id, claim_validity.ABSENT)
        judged = machine[content_id].get(claim_id)
        status = judged.status if judged is not None else None

        if verdict == GREY:
            grey += 1
        elif verdict not in (ACCEPT, REJECT):
            unanswered += 1
        elif status not in (claim_validity.SUPPORTED, claim_validity.REFUTED):
            insufficient += 1

        # The two lists are the same courses, in the same order, by construction — which is
        # what ADR-0063 §4 means by *the same proportion over the same 2x2*. A course the
        # assessor could not commit on carries human answers, and counting them towards the
        # ceiling while the judge is scored without them would measure the two halves of the
        # relative rule on different populations. That is not hypothetical where a format
        # feeds only half the criteria: there the whole other half would inflate the ceiling.
        committed = status if claim_validity.counts_in_table(verdict, status) else None
        if committed is not None:
            pairs.append((verdict, committed))
            per_rater.append(side.per_rater.get(quality_id, []))

        cell = claim_validity.discordant_cell(verdict, status) if status else None
        if cell is not None and judged is not None:
            answers = side.answers.get(quality_id, [])
            mean = statistics.fmean(answer.score for answer in answers)
            snapshot = courses.get(content_id)
            discordant.append(
                (
                    claim_validity.distance_from_cut(mean, thresholds),
                    DiscordantCourseDTO(
                        content_id=content_id,
                        external_id=snapshot.external_id if snapshot else "",
                        title=snapshot.title if snapshot else None,
                        cell=cell,
                        human_mean=mean,
                        experts_agree=claim_validity.verdicts_agree(
                            side.per_rater.get(quality_id, [])
                        ),
                        answers=answers,
                        evidence_basis=dict(judged.evidence_basis),
                        findings=raised.get((content_id, claim_id), []),
                    ),
                )
            )

    confusion = claim_validity.confuse(pairs)
    ceiling = claim_validity.pairwise_agreement(per_rater)
    verdict_of = claim_validity.classify(confusion, ceiling, thresholds)

    return ClaimValidityDTO(
        claim_id=claim_id,
        statement=statement,
        quality_id=quality_id,
        dimension=dimension,
        sample=confusion.total,
        sensitivity=claim_validity.sensitivity(confusion),
        specificity=claim_validity.specificity(confusion),
        kappa=claim_validity.cohen_kappa(confusion),
        youden_j=claim_validity.youden_j(confusion),
        judge_agreement=claim_validity.agreement(confusion),
        human_agreement=ceiling,
        grey=grey,
        unanswered=unanswered,
        insufficient=insufficient,
        status=verdict_of.status,
        reason=verdict_of.reason,
        # Widest disagreement first, and the campaign's order breaking ties so that two
        # readings of the same data list the same courses in the same places.
        discordant=[course for _, course in sorted(discordant, key=_widest_first)],
    )


def _widest_first(entry: tuple[float, DiscordantCourseDTO]) -> tuple[float, str]:
    distance, course = entry
    return (-distance, course.external_id)


def _empty(
    claim_id: str, statement: str, quality_id: str, dimension: str | None, reason: str
) -> ClaimValidityDTO:
    return ClaimValidityDTO(
        claim_id=claim_id,
        statement=statement,
        quality_id=quality_id,
        dimension=dimension,
        sample=0,
        sensitivity=Ratio(0, 0),
        specificity=Ratio(0, 0),
        kappa=None,
        youden_j=None,
        judge_agreement=None,
        human_agreement=None,
        grey=0,
        unanswered=0,
        insufficient=0,
        status=claim_validity.UNVALIDATED,
        reason=reason,
        discordant=[],
    )


__all__ = [
    "AssessorUnknown",
    "CitedFindingDTO",
    "ClaimValidityDTO",
    "ClaimValidityReportDTO",
    "Confusion",
    "DiscordantCourseDTO",
    "HumanAnswerDTO",
    "InstrumentNotPublished",
    "build_claim_validity",
]
