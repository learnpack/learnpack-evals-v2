"""SubmitEvaluation → EvaluationSubmitted (07-define.md, 08-code.md §5).

The core command of the MVP. Note what it does *not* do: it does not know about campaigns or
assignments, and it does not emit `ContentEvaluationCompleted`. Orchestration owns completion
and reacts to the event.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.application.ports import EvaluationRepositoryPort
from app.modules.evaluation.domain import events
from app.modules.evaluation.domain.evaluation import CriterionScore, Evaluation
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class ScoreInput:
    criterion_id: str
    score: int
    comment: str | None = None


@dataclass(frozen=True)
class SubmitEvaluationCommand:
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    scores: list[ScoreInput]
    # The rubric's criteria, passed in as plain data so the domain stays independent of
    # Rubric Authoring (ARCHITECTURE.md §3).
    rubric_criterion_ids: list[str]


class SubmitEvaluation:
    def __init__(
        self,
        evaluations: EvaluationRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._evaluations = evaluations
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: SubmitEvaluationCommand) -> Evaluation:
        evaluation = Evaluation.submit(
            evaluation_id=new_id(),
            assessor_id=command.assessor_id,
            content_id=command.content_id,
            instrument_version_id=command.instrument_version_id,
            scores=[
                CriterionScore(criterion_id=s.criterion_id, score=s.score, comment=s.comment)
                for s in command.scores
            ],
            rubric_criterion_ids=command.rubric_criterion_ids,
        )

        self._evaluations.add(evaluation)
        self._publisher.publish(events.evaluation_submitted(evaluation))
        # Evaluation + EvaluationResult are one transactional unit (07-define.md).
        self._uow.commit()
        return evaluation
