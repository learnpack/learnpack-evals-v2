"""Use case: PreviewEvaluation — the dry-run, the instrument-calibration tool.

Runs the exact same mechanics as EvaluateContent (derivation + executors + judgment
derivation) and persists NOTHING: no evaluation row, no events, no judgment. Accepts
drafts and needs no ratification — that is the point: iterate an instrument against real
content before publishing costs anything. The only prerequisite kept is the `ok` profile
(the automated path evaluates profiles, ADR-0015 — dry-run included).
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.application.evaluate_content import (
    InstrumentNotEvaluable,
    ProfileNotAvailable,
)
from app.modules.evaluation.application.ports import InstrumentGatewayPort, ProfileGatewayPort
from app.modules.evaluation.domain.derivation import (
    Executor,
    RunIndependently,
    derive_and_execute,
)
from app.modules.evaluation.domain.judgment import JudgmentDraft, derive_judgment
from app.modules.evaluation.domain.model import (
    ComputedMetric,
    Coverage,
    CriterionOutcome,
    InstrumentSpec,
)


@dataclass(frozen=True)
class PreviewEvaluationCommand:
    content_id: UUID
    instrument_version_id: str


@dataclass(frozen=True)
class Preview:
    instrument: InstrumentSpec
    outcomes: tuple[CriterionOutcome, ...]
    metrics: tuple[ComputedMetric, ...]
    judgment: JudgmentDraft


class PreviewEvaluation:
    def __init__(
        self,
        *,
        instruments: InstrumentGatewayPort,
        profiles: ProfileGatewayPort,
        coverage: Coverage,
        executors: dict[str, Executor],
        run_criteria: RunIndependently,
    ) -> None:
        self._instruments = instruments
        self._profiles = profiles
        self._coverage = coverage
        self._executors = executors
        # Declared by every caller, never defaulted: whether an evaluation's criteria are
        # looked at one at a time or together is a property of the run, and a default here
        # would decide it for whoever forgot to say (ADR-0048).
        self._run_criteria = run_criteria

    def __call__(self, command: PreviewEvaluationCommand) -> Preview:
        instrument = self._instruments.get_instrument(command.instrument_version_id)
        if instrument is None:
            raise InstrumentNotEvaluable(
                f"instrument version {command.instrument_version_id} not found"
            )
        profile = self._profiles.get_profile(command.content_id)
        if profile is None:
            raise ProfileNotAvailable(
                f"content {command.content_id} has no ok profile — profile it first"
            )
        outcomes, metrics = derive_and_execute(
            instrument,
            profile,
            self._preview_coverage(instrument),
            self._executors,
            self._run_criteria,
        )
        return Preview(
            instrument=instrument,
            outcomes=outcomes,
            metrics=metrics,
            judgment=derive_judgment(instrument, outcomes),
        )

    def _preview_coverage(self, instrument: InstrumentSpec) -> Coverage:
        """A draft may carry criteria this assessor does not cover yet; the real path
        rejects that at ratification (ADR-0019), the dry-run reports it as
        `not_assessed` — exactly the calibration signal the author is after."""
        uncovered = instrument.criterion_ids - self._coverage.declared
        if not uncovered:
            return self._coverage
        return Coverage(
            executes=self._coverage.executes,
            abstains={
                **self._coverage.abstains,
                **{c: "not covered by this assessor version (dry-run)" for c in uncovered},
            },
        )
