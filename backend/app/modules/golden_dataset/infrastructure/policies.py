"""Wires Golden Dataset's policy onto the dispatcher (ADR-0003).

This is the second link of the chain: `EvaluationSubmitted` → (orchestration)
`ContentEvaluationCompleted` → (golden) `GoldenReferenceEstablished`. This handler therefore
runs from inside Orchestration's own `uow.commit()`, and opens its own session — each policy
is its own transaction.
"""

from uuid import UUID

from app.modules.golden_dataset.application.establish_golden_reference import (
    CampaignCoverage,
    EstablishGoldenReference,
)
from app.modules.golden_dataset.infrastructure.repository import (
    SqlAlchemyGoldenReferenceRepository,
)
from app.modules.orchestration import public as orchestration_contract
from app.platform.db import SessionLocal
from app.platform.events import EventDispatcher
from app.platform.uow import UnitOfWork
from app.shared.domain.events import DomainEvent


def on_content_evaluation_completed(event: DomainEvent) -> None:
    campaign_id = UUID(event.payload["campaignId"])

    session = SessionLocal()
    try:
        # Coverage is Orchestration's to compute; usability is ours to judge.
        progress = orchestration_contract.OrchestrationQueries(session).get_campaign_progress(
            campaign_id
        )
        if progress is None:
            return

        uow = UnitOfWork(session)
        use_case = EstablishGoldenReference(
            references=SqlAlchemyGoldenReferenceRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        use_case(
            CampaignCoverage(
                campaign_id=campaign_id,
                rubric_version_id=progress.rubric_version_id,
                coverage=progress.coverage,
                threshold=progress.golden_coverage_threshold,
            )
        )
    finally:
        session.close()


def register_policies(dispatcher: EventDispatcher) -> None:
    dispatcher.subscribe(
        orchestration_contract.CONTENT_EVALUATION_COMPLETED, on_content_evaluation_completed
    )
