"""Policy: EvaluationCompleted → derive the QualityJudgment (13-code §5).

Self-subscription: the event and the reaction live in the same module — the judgment is
Evaluation's own projection of a completed act, not another module's concern. Pattern of
ADR-0003: the policy runs in its own transaction; idempotence by conditional insert on
`evaluation_id` (replaying a stored event derives nothing and re-emits nothing).
"""

from app.modules.evaluation import public as evaluation_contract
from app.modules.evaluation.application.derive_judgment import (
    DeriveJudgment,
    DeriveJudgmentCommand,
)
from app.modules.evaluation.infrastructure.gateways import DesignInstrumentGateway
from app.modules.evaluation.infrastructure.repository import (
    SqlAlchemyAutomatedEvaluationRepository,
    SqlAlchemyJudgmentRepository,
)
from app.platform.db import SessionLocal
from app.platform.events import EventDispatcher
from app.platform.uow import UnitOfWork
from app.shared.domain.events import DomainEvent


def on_evaluation_completed(event: DomainEvent) -> None:
    fact = evaluation_contract.EvaluationCompletedFact.from_payload(event.payload)
    session = SessionLocal()  # a policy runs in its own transaction (ADR-0003)
    try:
        uow = UnitOfWork(session)
        handler = DeriveJudgment(
            evaluations=SqlAlchemyAutomatedEvaluationRepository(session),
            instruments=DesignInstrumentGateway(session),
            judgments=SqlAlchemyJudgmentRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        handler(
            DeriveJudgmentCommand(
                evaluation_id=fact.evaluation_id,
                content_id=fact.content_id,
                instrument_version_id=fact.instrument_version_id,
            )
        )
    finally:
        session.close()


def register_policies(dispatcher: EventDispatcher) -> None:
    dispatcher.subscribe(evaluation_contract.EVALUATION_COMPLETED, on_evaluation_completed)
