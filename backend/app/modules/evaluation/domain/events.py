"""Domain events published by Evaluation (02-discover.md, phase 3; 13-code §3.5).

`EvaluationSubmitted` is the human workhorse: high frequency, NOT pivotal. Orchestration
reacts to it to mark assignments and detect completion — Evaluation itself never emits
`ContentEvaluationCompleted` (07-define.md, "Refinamiento vs Discover").

The automated path emits `EvaluationCompleted` (coordinates only — subscribers read the
outcomes via queries), and its judgment policy emits `QualityJudgmentPublished` +
`FindingRaised` under the QualityJudgment aggregate.
"""

from uuid import UUID

from app.modules.evaluation.domain.automated import AutomatedEvaluation
from app.modules.evaluation.domain.evaluation import Evaluation
from app.modules.evaluation.domain.judgment import FindingDraft
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "Evaluation"
JUDGMENT_AGGREGATE_TYPE = "QualityJudgment"

MODE_HUMAN = "human"
MODE_AUTOMATED = "automated"  # ADR-0016: the two kinds; the mechanism inside is not a mode


def evaluation_submitted(evaluation: Evaluation) -> DomainEvent:
    return DomainEvent(
        event_type="EvaluationSubmitted",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(evaluation.id),
        payload={
            "evaluationId": str(evaluation.id),
            # Provenance: which Assessor produced this judgement (GLOSSARY.md).
            "assessorId": str(evaluation.assessor_id),
            "contentId": str(evaluation.content_id),
            "instrumentVersionId": evaluation.instrument_version_id,
            "mode": MODE_HUMAN,
            "attempt": evaluation.attempt,
            "scores": [
                {"criterionId": s.criterion_id, "score": s.score, "comment": s.comment}
                for s in evaluation.result.scores
            ],
        },
    )


def evaluation_completed(evaluation: AutomatedEvaluation) -> DomainEvent:
    """Coordinates only: the judgment policy reloads outcomes from the tables."""
    return DomainEvent(
        event_type="EvaluationCompleted",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(evaluation.id),
        payload={
            "evaluationId": str(evaluation.id),
            "assessorId": str(evaluation.assessor_id),
            "contentId": str(evaluation.content_id),
            "instrumentVersionId": evaluation.instrument_version_id,
            "profileId": str(evaluation.profile_id),
            "mode": MODE_AUTOMATED,
            "attempt": evaluation.attempt,
        },
    )


def quality_judgment_published(
    judgment_id: UUID,
    evaluation_id: UUID,
    content_id: UUID,
    instrument_version_id: str,
) -> DomainEvent:
    return DomainEvent(
        event_type="QualityJudgmentPublished",
        aggregate_type=JUDGMENT_AGGREGATE_TYPE,
        aggregate_id=str(judgment_id),
        payload={
            "judgmentId": str(judgment_id),
            "evaluationId": str(evaluation_id),
            "contentId": str(content_id),
            "instrumentVersionId": instrument_version_id,
        },
    )


def finding_raised(
    judgment_id: UUID, finding_id: UUID, content_id: UUID, finding: FindingDraft
) -> DomainEvent:
    return DomainEvent(
        event_type="FindingRaised",
        aggregate_type=JUDGMENT_AGGREGATE_TYPE,
        aggregate_id=str(judgment_id),
        payload={
            "findingId": str(finding_id),
            "judgmentId": str(judgment_id),
            "contentId": str(content_id),
            "claimId": finding.claim_id,
            "criterionId": finding.criterion_id,
            "failureMode": finding.failure_mode,
        },
    )
