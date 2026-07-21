"""Domain events published by Evaluation (02-discover.md, phase 3).

`EvaluationSubmitted` is the workhorse: high frequency, NOT pivotal. Orchestration reacts to
it to mark assignments and detect completion — Evaluation itself never emits
`ContentEvaluationCompleted` (07-define.md, "Refinamiento vs Discover").
"""

from app.modules.evaluation.domain.evaluation import Evaluation
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "Evaluation"

# The MVP has a single EvaluationSource type; the slot stays open for LLMJudge [futuro].
MODE_HUMAN = "human"


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
            "rubricVersionId": evaluation.rubric_version_id,
            "mode": MODE_HUMAN,
            "attempt": evaluation.attempt,
            "scores": [
                {"criterionId": s.criterion_id, "score": s.score, "comment": s.comment}
                for s in evaluation.result.scores
            ],
        },
    )
