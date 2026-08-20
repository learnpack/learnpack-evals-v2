"""Use case: EvaluateContent — the real automated path (13-code §3.5).

Guards, in order: the instrument version must be published (drafts are calibrated with
the dry-run) · the assessor must have that version ratified (ADR-0019) · the content
must have an `ok` profile (ADR-0015: the automated path evaluates a profile, never raw
content). Then the mechanical derivation runs, executors judge the judgeables, and the
completed evaluation persists with `EvaluationCompleted` — the judgment policy takes it
from there.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.application.ports import (
    AutomatedEvaluationRepositoryPort,
    InstrumentGatewayPort,
    ProfileGatewayPort,
    RatificationRepositoryPort,
)
from app.modules.evaluation.domain import events
from app.modules.evaluation.domain.automated import AutomatedEvaluation
from app.modules.evaluation.domain.derivation import (
    Executor,
    RunIndependently,
    derive_and_execute,
)
from app.modules.evaluation.domain.model import Coverage
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class InstrumentNotEvaluable(Exception):
    """Unknown version, or a draft — publish first (drafts calibrate via dry-run)."""


class AssessorNotRatified(Exception):
    """The assessor has not ratified this instrument version (ADR-0019)."""


class ProfileNotAvailable(Exception):
    """No `ok` profile for the content — profile it first (ADR-0015 prerequisite)."""


@dataclass(frozen=True)
class EvaluateContentCommand:
    content_id: UUID
    instrument_version_id: str
    assessor_id: UUID


class EvaluateContent:
    def __init__(
        self,
        *,
        evaluations: AutomatedEvaluationRepositoryPort,
        instruments: InstrumentGatewayPort,
        profiles: ProfileGatewayPort,
        ratifications: RatificationRepositoryPort,
        coverage: Coverage,
        executors: dict[str, Executor],
        run_criteria: RunIndependently,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._evaluations = evaluations
        self._instruments = instruments
        self._profiles = profiles
        self._ratifications = ratifications
        self._coverage = coverage
        self._executors = executors
        # Declared by every caller, never defaulted: whether an evaluation's criteria are
        # looked at one at a time or together is a property of the run, and a default here
        # would decide it for whoever forgot to say (ADR-0048).
        self._run_criteria = run_criteria
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: EvaluateContentCommand) -> AutomatedEvaluation:
        instrument = self._instruments.get_instrument(command.instrument_version_id)
        if instrument is None:
            raise InstrumentNotEvaluable(
                f"instrument version {command.instrument_version_id} not found"
            )
        if not instrument.is_published:
            raise InstrumentNotEvaluable(
                f"{instrument.instrument_version_id} is {instrument.status}: only "
                "published versions are evaluable — calibrate drafts with --dry-run"
            )
        if not self._ratifications.is_ratified(command.assessor_id, command.instrument_version_id):
            raise AssessorNotRatified(
                f"the assessor has not ratified {command.instrument_version_id} "
                "(ADR-0019) — run ratify-assessor first"
            )
        profile = self._profiles.get_profile(command.content_id)
        if profile is None:
            raise ProfileNotAvailable(
                f"content {command.content_id} has no ok profile — profile it first"
            )

        outcomes, metrics = derive_and_execute(
            instrument, profile, self._coverage, self._executors, self._run_criteria
        )
        evaluation = AutomatedEvaluation.complete(
            evaluation_id=new_id(),
            assessor_id=command.assessor_id,
            content_id=command.content_id,
            instrument=instrument,
            profile_id=profile.profile_id,
            outcomes=outcomes,
            metrics=metrics,
            attempt=self._evaluations.next_attempt(
                command.assessor_id, command.content_id, command.instrument_version_id
            ),
        )
        self._evaluations.add(evaluation)
        self._publisher.publish(events.evaluation_completed(evaluation))
        self._uow.commit()
        return evaluation
