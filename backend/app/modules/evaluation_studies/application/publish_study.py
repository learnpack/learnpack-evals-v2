"""Use case: publish the study — the human act that materializes the immutable report.

Composed on-read via the gateway ports (ADR-0006 style: batch queries, aggregation in
Python, no projection tables) and written once — `insert_once` makes re-publication
impossible at the row level too.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

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
        instrument = self._design.get_instrument(study.instrument_version_id)
        if instrument is None:
            raise UnknownInstrument(
                f"instrument version {study.instrument_version_id} does not exist"
            )

        content_ids = list(study.content_ids)
        contents = self._registry.get_contents_by_ids(content_ids)

        briefs = {}
        for brief_id in {c.brief_id for c in contents if c.brief_id is not None}:
            brief = self._registry.get_brief(brief_id)
            if brief is not None:
                briefs[brief_id] = brief

        generators = {}
        for generator_id in {
            c.generator_version_id for c in contents if c.generator_version_id is not None
        }:
            generator = self._registry.get_generator(generator_id)
            if generator is not None:
                generators[generator_id] = generator

        capabilities = {
            package_format: self._profiling.get_capabilities(package_format)
            for package_format in {c.package_format for c in contents}
        }

        return compose_report(
            study=study,
            contents=contents,
            briefs=briefs,
            generators=generators,
            judgments=self._evaluation.get_judgments(content_ids, study.instrument_version_id),
            findings=self._evaluation.get_findings(content_ids, study.instrument_version_id),
            capabilities=capabilities,
            instrument=instrument,
            published_at=now,
        )
