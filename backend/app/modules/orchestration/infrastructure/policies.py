"""Wires the completion policy onto the event dispatcher (ADR-0003).

The handler runs **after** the evaluation's transaction committed, so it opens its own
session: completion is eventually consistent, not an invariant of a big aggregate (ADR-0002).
"""

from app.modules.evaluation import public as evaluation_contract
from app.modules.orchestration.application.completion_policy import (
    EvaluationSubmittedFact,
    HandleEvaluationSubmitted,
)
from app.modules.orchestration.infrastructure.repository import (
    SqlAlchemyAssignmentRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyCompletionRepository,
)
from app.platform.db import SessionLocal
from app.platform.events import EventDispatcher
from app.platform.uow import UnitOfWork
from app.shared.domain.events import DomainEvent


def on_evaluation_submitted(event: DomainEvent) -> None:
    # Translate the publisher's contract into orchestration's own input at the boundary,
    # so the application layer never depends on the Evaluation module.
    published = evaluation_contract.EvaluationSubmittedFact.from_payload(event.payload)
    fact = EvaluationSubmittedFact(
        content_id=published.content_id,
        assignment_id=published.assignment_id,
    )

    session = SessionLocal()
    try:
        uow = UnitOfWork(session)
        handler = HandleEvaluationSubmitted(
            campaigns=SqlAlchemyCampaignRepository(session),
            assignments=SqlAlchemyAssignmentRepository(session),
            completions=SqlAlchemyCompletionRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        handler(fact)
    finally:
        session.close()


def register_policies(dispatcher: EventDispatcher) -> None:
    dispatcher.subscribe(evaluation_contract.EVALUATION_SUBMITTED, on_evaluation_submitted)
