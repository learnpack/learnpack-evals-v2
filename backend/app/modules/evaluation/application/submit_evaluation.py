"""SubmitEvaluation → EvaluationSubmitted (07-define.md, 08-code.md §5).

The core command of the MVP. Note what it does *not* do: it does not know about **campaigns**,
and it does not emit `ContentEvaluationCompleted` — Orchestration owns completion and reacts to
the event.

It does know which **assignment** it answers (ADR-0065), and records it. That is the link
ADR-0002 always named; what changed is that it is stored rather than reconstructed later from
`(content, assessor)`, which could not tell one round's answer from another's.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.application.ports import EvaluationRepositoryPort
from app.modules.evaluation.domain import events
from app.modules.evaluation.domain.evaluation import Evaluation, ItemScore
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class ScoreInput:
    quality_id: str
    score: int | None
    comment: str | None = None
    # True only for rows the mechanics produced for a withheld item (ADR-0053). The router
    # mints those; a client cannot set it, because a rater may not declare their own answer
    # mechanical.
    derived: bool = False


@dataclass(frozen=True)
class SubmitEvaluationCommand:
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    # Which assignment this answers. Required on the human path — the endpoint has it — and
    # absent only where no assignment exists, which is the automated path (ADR-0065 §1).
    assignment_id: UUID
    scores: list[ScoreInput]
    # The rubric's items, passed in as plain data so the domain stays independent of
    # Rubric Authoring (ARCHITECTURE.md §3).
    rubric_quality_ids: list[str]


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
            assignment_id=command.assignment_id,
            scores=[
                ItemScore(
                    quality_id=s.quality_id,
                    score=s.score,
                    comment=s.comment,
                    derived=s.derived,
                )
                for s in command.scores
            ],
            rubric_quality_ids=command.rubric_quality_ids,
        )

        self._evaluations.add(evaluation)
        self._publisher.publish(events.evaluation_submitted(evaluation))
        # Evaluation + EvaluationResult are one transactional unit (07-define.md).
        self._uow.commit()
        return evaluation
