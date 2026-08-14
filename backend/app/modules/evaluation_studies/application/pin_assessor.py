"""Use case: pin the assessor — ONCE, before opening (ADR-0042 §8).

The second half of the reproducibility commitment the instrument pin starts. From here the
study's result is a triple — this dataset, that norm, this judge — and every read of it
counts only what this assessor produced. A judgment by anybody else is not part of this
study's result; it is not deleted, it simply does not answer here.

The one check that is not the aggregate's: **the assessor must have ratified the pinned
instrument version** (ADR-0019). Pinning an assessor that cannot legally persist a judgment
would create a study nothing can evaluate, which is the shape of refusal ADR-0036 argues
against offering at all — so it is refused at the gate rather than discovered at the batch.
It also means the instrument is pinned first: without a version there is nothing to ratify
against.

Ratification is read through `list_ratifications`, which the port already publishes for
readiness. Membership in that list answers both questions at once — an assessor with a
ratification row necessarily exists — so no new port method and no second module.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation_studies.application.ports import (
    EvaluationGatewayPort,
    StudyRepositoryPort,
)
from app.modules.evaluation_studies.domain import events
from app.modules.evaluation_studies.domain.model import Study, StudyNotFound
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class InstrumentPinnedFirst(Exception):
    """The assessor is pinned against a norm; without one there is nothing to check."""


class AssessorHasNotRatified(Exception):
    """This assessor has not ratified the pinned version, so it could persist nothing."""


@dataclass(frozen=True)
class PinAssessorCommand:
    study_id: UUID
    assessor_id: UUID


class PinAssessor:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        evaluation: EvaluationGatewayPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._evaluation = evaluation
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: PinAssessorCommand) -> Study:
        study = self._studies.get_by_id(command.study_id)
        if study is None:
            raise StudyNotFound(f"study {command.study_id} is not declared")

        version_id = study.instrument_version_id
        if version_id is None:
            raise InstrumentPinnedFirst(
                f"study {study.id} pins no instrument version; pin one before its assessor"
            )

        ratified = {r.assessor_id for r in self._evaluation.list_ratifications(version_id)}
        if command.assessor_id not in ratified:
            raise AssessorHasNotRatified(
                f"assessor {command.assessor_id} has not ratified {version_id} (ADR-0019); "
                "ratify it first — without that it could persist no judgment for this study"
            )

        study.pin_assessor(command.assessor_id)
        self._studies.update(study)
        self._publisher.publish(events.assessor_pinned(study))
        self._uow.commit()
        return study
