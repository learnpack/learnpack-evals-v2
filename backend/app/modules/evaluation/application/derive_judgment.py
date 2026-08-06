"""Policy use case: derive the QualityJudgment from a completed evaluation.

Runs in the judgment policy's own transaction (ADR-0003 pattern). Idempotent by
conditional insert on `evaluation_id` — replaying `EvaluationCompleted` derives nothing
new and re-emits nothing. Events (`QualityJudgmentPublished` + one `FindingRaised` per
finding) go out only when the judgment was actually recorded.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.application.ports import (
    AutomatedEvaluationRepositoryPort,
    InstrumentGatewayPort,
    JudgmentRecord,
    JudgmentRepositoryPort,
)
from app.modules.evaluation.domain import events
from app.modules.evaluation.domain.judgment import derive_judgment
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class EvaluationNotFound(Exception):
    """No outcomes for that evaluation — nothing to judge."""


@dataclass(frozen=True)
class DeriveJudgmentCommand:
    evaluation_id: UUID
    content_id: UUID
    instrument_version_id: str


class DeriveJudgment:
    def __init__(
        self,
        *,
        evaluations: AutomatedEvaluationRepositoryPort,
        instruments: InstrumentGatewayPort,
        judgments: JudgmentRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._evaluations = evaluations
        self._instruments = instruments
        self._judgments = judgments
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: DeriveJudgmentCommand) -> bool:
        """True when the judgment was newly derived; False on replay."""
        outcomes = self._evaluations.get_outcomes(command.evaluation_id)
        if not outcomes:
            raise EvaluationNotFound(f"no outcomes for evaluation {command.evaluation_id}")
        instrument = self._instruments.get_instrument(command.instrument_version_id)
        if instrument is None:
            raise EvaluationNotFound(
                f"instrument version {command.instrument_version_id} not found"
            )

        draft = derive_judgment(instrument, outcomes)
        record = JudgmentRecord(
            judgment_id=new_id(),
            evaluation_id=command.evaluation_id,
            content_id=command.content_id,
            instrument_version_id=command.instrument_version_id,
            coverage=draft.coverage,
            claims=draft.claims,
            findings=tuple((new_id(), finding) for finding in draft.findings),
        )
        newly_recorded = self._judgments.insert(record)
        if newly_recorded:
            # Publish only if we actually recorded it — replays must not re-emit.
            self._publisher.publish(
                events.quality_judgment_published(
                    record.judgment_id,
                    record.evaluation_id,
                    record.content_id,
                    record.instrument_version_id,
                )
            )
            for finding_id, finding in record.findings:
                self._publisher.publish(
                    events.finding_raised(
                        record.judgment_id, finding_id, record.content_id, finding
                    )
                )
        self._uow.commit()
        return newly_recorded
