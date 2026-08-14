"""Use case: publish the study — the human act that materializes the immutable report.

Composed on-read via the gateway ports (ADR-0006 style: batch queries, aggregation in
Python, no projection tables) and written once — `insert_once` makes re-publication
impossible at the row level too.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.modules.evaluation_studies.application.gathering import gather_report_inputs
from app.modules.evaluation_studies.application.pin_instrument import UnknownInstrument
from app.modules.evaluation_studies.application.ports import (
    DesignGatewayPort,
    EvaluationGatewayPort,
    ProfilingGatewayPort,
    RegistryGatewayPort,
    StudyReportRepositoryPort,
    StudyRepositoryPort,
)
from app.modules.evaluation_studies.application.report import compose_report
from app.modules.evaluation_studies.domain import events
from app.modules.evaluation_studies.domain.model import (
    Study,
    StudyAlreadyPublished,
    StudyNotFound,
)
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


@dataclass(frozen=True)
class PublishStudyCommand:
    study_id: UUID
    published_by: UUID


class PublishStudy:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        reports: StudyReportRepositoryPort,
        registry: RegistryGatewayPort,
        evaluation: EvaluationGatewayPort,
        design: DesignGatewayPort,
        profiling: ProfilingGatewayPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._reports = reports
        self._registry = registry
        self._evaluation = evaluation
        self._design = design
        self._profiling = profiling
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: PublishStudyCommand) -> Study:
        study = self._studies.get_by_id(command.study_id)
        if study is None:
            raise StudyNotFound(f"study {command.study_id} is not declared")

        now = datetime.now(UTC)
        study.publish(command.published_by, now)

        report = self._compose(study, now)
        if not self._reports.insert_once(study.id, report, now):
            raise StudyAlreadyPublished(f"study {study.id} already has a report")

        self._studies.update(study)
        judgment_ids = [UUID(j) for j in report["judgmentIdsUsed"].values()]
        self._publisher.publish(events.study_published(study, judgment_ids))
        self._uow.commit()
        return study

    def _compose(self, study: Study, now: datetime) -> dict[str, Any]:
        assert study.instrument_version_id is not None  # guaranteed: open requires the pin
        inputs = gather_report_inputs(
            study, self._registry, self._evaluation, self._design, self._profiling
        )
        if inputs.instrument is None:
            # The gathering reports the absence; refusing to publish over it is THIS
            # caller's rule — a preview reports the same absence as a gap and answers.
            raise UnknownInstrument(
                f"instrument version {study.instrument_version_id} does not exist"
            )

        return compose_report(
            study=study,
            contents=inputs.contents,
            briefs=inputs.briefs,
            generators=inputs.generators,
            judgments=inputs.judgments,
            findings=inputs.findings,
            capabilities=inputs.capabilities,
            instrument=inputs.instrument,
            published_at=now,
        )
