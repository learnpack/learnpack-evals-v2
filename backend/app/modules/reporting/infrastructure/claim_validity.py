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

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.public import EvaluationQueries, QualityJudgmentDTO
from app.modules.evaluation_design.public import InstrumentQueries, RubricQueries
from app.modules.identity.public import IdentityQueries
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

    names = identity.list_assessors([assessor_id])
    if assessor_id not in names:
        raise AssessorUnknown(str(assessor_id))
    assessor = names[assessor_id]

    campaign = answers.campaign
    elicited = {item.quality_id for item in answers.rubric.items}

    judgments = _latest_per_content(
        evaluations.get_judgments(campaign.content_ids, instrument_version_id, assessor_id)
    )
    # The sample: the campaign's courses this assessor also judged. Ordered so the numbers do
    # not depend on dictionary insertion.
    sample_ids = [cid for cid in campaign.content_ids if cid in judgments]

    human = {cid: _human_side(answers.counted.get(cid, []), thresholds) for cid in sample_ids}
    machine = {cid: _claim_status(judgments[cid]) for cid in sample_ids}

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


def _human_side(evaluations: list, thresholds: Thresholds) -> _HumanSide:
    scores: dict[str, list[int]] = {}
    for evaluation in evaluations:
        for score in evaluation.scores:
            # An abstention and a derived row are not judgements (ADR-0052 §4, ADR-0053), so
            # neither reaches the cut.
            if score.score is None or score.derived:
                continue
            scores.setdefault(score.quality_id, []).append(score.score)
    return _HumanSide(
        verdict={q: claim_validity.human_verdict(s, thresholds) for q, s in scores.items()},
        per_rater={q: claim_validity.rater_verdicts(s, thresholds) for q, s in scores.items()},
    )


def _claim_status(judgment: QualityJudgmentDTO) -> dict[str, str]:
    return {claim.claim_id: claim.status for claim in judgment.claims}


def _validity_of(
    *,
    claim_id: str,
    statement: str,
    quality_id: str,
    dimension: str | None,
    elicited: set[str],
    sample_ids: list[UUID],
    human: dict[UUID, _HumanSide],
    machine: dict[UUID, dict[str, str]],
    thresholds: Thresholds,
) -> ClaimValidityDTO:
    if quality_id not in elicited:
        # The reference instrument does not ask about this quality, so there is no human
        # column to compare against — and no campaign fixes that.
        return _empty(claim_id, statement, quality_id, dimension, "no_reference_item")

    pairs: list[tuple[HumanVerdict, str]] = []
    per_rater: list[list[HumanVerdict]] = []
    grey = unanswered = insufficient = 0

    for content_id in sample_ids:
        verdict = human[content_id].verdict.get(quality_id, claim_validity.ABSENT)
        status = machine[content_id].get(claim_id)
        per_rater.append(human[content_id].per_rater.get(quality_id, []))

        if verdict == GREY:
            grey += 1
        elif verdict not in (ACCEPT, REJECT):
            unanswered += 1
        elif status not in (claim_validity.SUPPORTED, claim_validity.REFUTED):
            insufficient += 1
        if status is not None:
            pairs.append((verdict, status))

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
    )


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
    )


__all__ = [
    "AssessorUnknown",
    "ClaimValidityDTO",
    "ClaimValidityReportDTO",
    "Confusion",
    "InstrumentNotPublished",
    "build_claim_validity",
]
