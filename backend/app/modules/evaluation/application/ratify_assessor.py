"""Use case: RatifyAssessor — the ADR-0019 act, at whichever gate asks for it.

Ratifying makes one instrument version evaluable by one assessor, and nothing else: the
assessor's identity is its artifact (ADR-0016 §2) and is untouched here. Initial
registration IS the first ratification, so the first call over a lineage has no diff to
compute; against a later version the diff is mechanical — a criterion whose normative text
(`pass_condition` + `required_data`, compared literally) is unchanged carries its coverage
over, a new or changed **executed** one demands an explicit decision by criterion id, and a
changed **abstained** one is informational, because an abstention realizes no normative
text (ADR-0019 §3).

The refusals carry facts, not sentences: each gate writes its own message (ADR-0036 §4) —
the CLI an exit code and a line on stderr, the console a status code and a detail object.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation.application.ports import (
    InstrumentGatewayPort,
    RatificationRepositoryPort,
)
from app.modules.evaluation.domain.model import Coverage, InstrumentSpec
from app.shared.application.ports import UnitOfWorkPort


class RatificationRefused(Exception):
    """Base of every reason the act cannot proceed."""


class InstrumentVersionUnknown(RatificationRefused):
    def __init__(self, instrument_version_id: str) -> None:
        super().__init__(f"instrument version {instrument_version_id} not found")
        self.instrument_version_id = instrument_version_id


class ForeignLineage(RatificationRefused):
    """The assessor owes itself to another lineage — coverage is declared over ids that
    mean nothing in this one (ADR-0019 §1)."""

    def __init__(self, expected_instrument_id: str, actual_instrument_id: str) -> None:
        super().__init__(
            f"the assessor owes itself to lineage '{expected_instrument_id}', "
            f"not '{actual_instrument_id}'"
        )
        self.expected_instrument_id = expected_instrument_id
        self.actual_instrument_id = actual_instrument_id


class InstrumentVersionNotPublished(RatificationRefused):
    """Drafts are calibrated with the dry-run; only a published version is ratifiable."""

    def __init__(self, instrument_version_id: str, status: str) -> None:
        super().__init__(f"{instrument_version_id} is {status}")
        self.instrument_version_id = instrument_version_id
        self.status = status


class CoverageIncomplete(RatificationRefused):
    """Some criterion of the version is neither executed nor abstained (ADR-0018)."""

    def __init__(self, undecided: frozenset[str]) -> None:
        super().__init__(f"coverage does not decide: {', '.join(sorted(undecided))}")
        self.undecided = undecided


@dataclass(frozen=True)
class CriterionDelta:
    """One criterion the target version does not share with the previously ratified one."""

    criterion_id: str
    change: str  # new | changed
    pass_condition: str
    disposition: str  # abstained | confirmed | needs_confirmation


class RatificationNeedsConfirmation(RatificationRefused):
    """Executed criteria changed: each one needs its own decision (ADR-0019 §3)."""

    def __init__(self, previous_version_id: str, deltas: tuple[CriterionDelta, ...]) -> None:
        pending = tuple(d for d in deltas if d.disposition == "needs_confirmation")
        super().__init__(
            f"executed criteria changed since {previous_version_id}: "
            f"{', '.join(d.criterion_id for d in pending)}"
        )
        self.previous_version_id = previous_version_id
        # Every delta, so the caller can report the ones already decided the same way a
        # successful run would have.
        self.deltas = deltas
        self.pending = pending


@dataclass(frozen=True)
class RatifyAssessorCommand:
    assessor_id: UUID
    instrument_id: str
    instrument_version_id: str
    coverage: Coverage
    ratified_by: UUID
    confirmed: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Ratification:
    instrument_version_id: str
    # False when the version was already ratified: the act is idempotent, and saying so is
    # not the same as saying it just happened.
    newly_ratified: bool
    previous_version_id: str | None
    deltas: tuple[CriterionDelta, ...]


class RatifyAssessor:
    def __init__(
        self,
        *,
        instruments: InstrumentGatewayPort,
        ratifications: RatificationRepositoryPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._instruments = instruments
        self._ratifications = ratifications
        self._uow = uow

    def __call__(self, command: RatifyAssessorCommand) -> Ratification:
        target = self._instruments.get_instrument(command.instrument_version_id)
        if target is None:
            raise InstrumentVersionUnknown(command.instrument_version_id)
        if target.instrument_id != command.instrument_id:
            raise ForeignLineage(command.instrument_id, target.instrument_id)
        if not target.is_published:
            raise InstrumentVersionNotPublished(target.instrument_version_id, target.status)

        # Coverage restricted to this version must decide every criterion (ADR-0018).
        undecided = target.criterion_ids - command.coverage.declared
        if undecided:
            raise CoverageIncomplete(undecided)

        previous_id = self._ratifications.latest_ratified(
            command.assessor_id,
            [
                version_id
                for version_id in self._instruments.list_version_ids(command.instrument_id)
                if version_id != target.instrument_version_id
            ],
        )
        deltas: tuple[CriterionDelta, ...] = ()
        if previous_id is not None:
            deltas = self._diff(target, previous_id, command)
            if any(d.disposition == "needs_confirmation" for d in deltas):
                raise RatificationNeedsConfirmation(previous_id, deltas)

        newly = self._ratifications.insert(
            command.assessor_id, target.instrument_version_id, command.ratified_by
        )
        self._uow.commit()
        return Ratification(
            instrument_version_id=target.instrument_version_id,
            newly_ratified=newly,
            previous_version_id=previous_id,
            deltas=deltas,
        )

    def _diff(
        self, target: InstrumentSpec, previous_id: str, command: RatifyAssessorCommand
    ) -> tuple[CriterionDelta, ...]:
        """What changed since the last ratified version of the lineage, and who decides it."""
        previous = self._instruments.get_instrument(previous_id)
        assert previous is not None  # ratifications FK to instrument_versions
        before = {c.criterion_id: c for c in previous.criteria}

        deltas = []
        for criterion in target.criteria:
            prior = before.get(criterion.criterion_id)
            if (
                prior is not None
                and prior.pass_condition == criterion.pass_condition
                and prior.required_data == criterion.required_data
            ):
                continue
            if criterion.criterion_id in command.coverage.abstains:
                disposition = "abstained"
            elif criterion.criterion_id in command.confirmed:
                disposition = "confirmed"
            else:
                disposition = "needs_confirmation"
            deltas.append(
                CriterionDelta(
                    criterion_id=criterion.criterion_id,
                    change="new" if prior is None else "changed",
                    pass_condition=criterion.pass_condition,
                    disposition=disposition,
                )
            )
        return tuple(deltas)
