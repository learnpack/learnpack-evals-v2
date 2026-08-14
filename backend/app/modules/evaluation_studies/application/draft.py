"""Use cases: declare a study, and change one while it is still a draft (ADR-0043 §1).

Three acts became one surface, because they were never three acts to a person: the
instrument, the judge and the dataset are chosen together and stay changeable until `open`
pins them. What replaced `PinInstrument`, `PinAssessor` and `ComposeDataset` is a single
selection, applied by `_apply` and shared by both use cases, so creating a study with
everything and correcting one field of it a day later run the same checks.

The checks did not change with the ceremony:

* the instrument version must exist and be **published** — a draft is still someone else's
  to edit (ADR-0012's lifecycle);
* the judge must have **ratified** the chosen version (ADR-0019), because one that has not
  could persist no judgment for this study;
* every brief must be registered, and the dataset it materializes is what `open` fixes.

`UNCHANGED` is the sentinel that distinguishes "the caller said nothing about this" from
"the caller cleared it" — `None` means clear, which is what re-pointing a draft at a norm
the current judge never ratified leaves behind.
"""

from dataclasses import dataclass, field
from typing import Any, Final
from uuid import UUID

from app.modules.evaluation_studies.application.ports import (
    DesignGatewayPort,
    EvaluationGatewayPort,
    RegistryGatewayPort,
    StudyRepositoryPort,
)
from app.modules.evaluation_studies.domain import events
from app.modules.evaluation_studies.domain.model import Study, StudyNotFound
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class UnknownInstrument(Exception):
    """No instrument version with that id."""


class InstrumentNotPublished(Exception):
    """Only a published version is choosable — a study never judges against a draft."""


class UnknownBrief(Exception):
    """A brief in the recipe is not registered."""


class InstrumentRequiredFirst(Exception):
    """A judge is checked against a norm; without one there is nothing to check."""


class AssessorHasNotRatified(Exception):
    """This judge has not ratified the chosen version, so it could persist nothing."""


class _Unchanged:
    """Absent from the request, as opposed to explicitly cleared."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNCHANGED"


UNCHANGED: Final = _Unchanged()


@dataclass(frozen=True)
class StudySelection:
    """What a draft may say about itself. Every field optional, `UNCHANGED` by default."""

    instrument_version_id: str | _Unchanged = UNCHANGED
    assessor_id: UUID | None | _Unchanged = UNCHANGED
    brief_ids: list[UUID] | _Unchanged = UNCHANGED


@dataclass(frozen=True)
class DeclareStudyCommand:
    name: str
    description: str | None = None
    selection: StudySelection = field(default_factory=StudySelection)


@dataclass(frozen=True)
class UpdateStudyDraftCommand:
    study_id: UUID
    name: str | _Unchanged = UNCHANGED
    description: str | None | _Unchanged = UNCHANGED
    selection: StudySelection = field(default_factory=StudySelection)


class _Selecting:
    """The half both use cases share: validate, then move the aggregate."""

    def __init__(
        self,
        registry: RegistryGatewayPort,
        design: DesignGatewayPort,
        evaluation: EvaluationGatewayPort,
    ) -> None:
        self._registry = registry
        self._design = design
        self._evaluation = evaluation

    def apply(self, study: Study, selection: StudySelection) -> None:
        if not isinstance(selection.instrument_version_id, _Unchanged):
            self._check_instrument(selection.instrument_version_id)
            study.select_instrument(selection.instrument_version_id)

        # After the instrument, always: the ratification is checked against the version the
        # study ends up with, not the one it had when the request was written.
        if not isinstance(selection.assessor_id, _Unchanged):
            if selection.assessor_id is not None:
                self._check_ratified(study, selection.assessor_id)
            study.select_assessor(selection.assessor_id)
        elif study.assessor_id is not None and not isinstance(
            selection.instrument_version_id, _Unchanged
        ):
            # The instrument moved under a judge the caller did not mention. Refused rather
            # than silently dropped: which of the two the caller meant is not ours to guess,
            # and the console never sends this because it clears the judge itself.
            self._check_ratified(study, study.assessor_id)

        if not isinstance(selection.brief_ids, _Unchanged):
            study.compose_dataset(*self._materialize(selection.brief_ids))

    def _check_instrument(self, instrument_version_id: str) -> None:
        instrument = self._design.get_instrument(instrument_version_id)
        if instrument is None:
            raise UnknownInstrument(f"instrument version {instrument_version_id} does not exist")
        if not instrument.is_published:
            raise InstrumentNotPublished(
                f"instrument version {instrument_version_id} is {instrument.status}; "
                "publish it before a study judges against it"
            )

    def _check_ratified(self, study: Study, assessor_id: UUID) -> None:
        version_id = study.instrument_version_id
        if version_id is None:
            raise InstrumentRequiredFirst(
                f"study {study.id} has no instrument version; choose one before its judge"
            )
        ratified = {r.assessor_id for r in self._evaluation.list_ratifications(version_id)}
        if assessor_id not in ratified:
            raise AssessorHasNotRatified(
                f"assessor {assessor_id} has not ratified {version_id} (ADR-0019); "
                "ratify it first, or choose another judge — without that it could persist "
                "no judgment for this study"
            )

    def _materialize(self, brief_ids: list[UUID]) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
        """The recipe (briefIds) selects contents through the registry; what comes back is
        the dataset, replaceable until `open` fixes it."""
        for brief_id in brief_ids:
            if self._registry.get_brief(brief_id) is None:
                raise UnknownBrief(f"brief {brief_id} is not registered")
        contents = self._registry.get_contents_by_briefs(brief_ids)
        return tuple(brief_ids), tuple(c.content_id for c in contents)


class DeclareStudy:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        registry: RegistryGatewayPort,
        design: DesignGatewayPort,
        evaluation: EvaluationGatewayPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._selecting = _Selecting(registry, design, evaluation)
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: DeclareStudyCommand) -> Study:
        study = Study(id=new_id(), name=command.name, description=command.description)
        # Validated before the row exists: a refusal leaves nothing behind to clean up.
        self._selecting.apply(study, command.selection)
        self._studies.add(study)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.study_declared(study))
        self._uow.commit()
        return study


class UpdateStudyDraft:
    """Change any part of a draft. Refused once the study is open — that is the pin."""

    def __init__(
        self,
        studies: StudyRepositoryPort,
        registry: RegistryGatewayPort,
        design: DesignGatewayPort,
        evaluation: EvaluationGatewayPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._selecting = _Selecting(registry, design, evaluation)
        self._uow = uow

    def __call__(self, command: UpdateStudyDraftCommand) -> Study:
        study = self._studies.get_by_id(command.study_id)
        if study is None:
            raise StudyNotFound(f"study {command.study_id} is not declared")

        if not isinstance(command.name, _Unchanged):
            _rename(study, command.name)
        if not isinstance(command.description, _Unchanged):
            study.description = command.description

        self._selecting.apply(study, command.selection)
        self._studies.update(study)
        # No event: nothing here is binding until `open` (ADR-0043 §2).
        self._uow.commit()
        return study


def _rename(study: Study, name: str) -> None:
    """Through `__post_init__` so a blank name is refused on the way in as on the way up:
    the aggregate owns that rule and there is no second copy of it here."""
    study.name = name
    study.__post_init__()


def selection_from(payload: dict[str, Any]) -> StudySelection:
    """Build a selection from a partial payload — a key that is absent stays `UNCHANGED`.

    Adapters (HTTP, CLI) decide what "absent" means for their own transport and hand the
    result here; the use cases never see a request object.
    """
    return StudySelection(
        instrument_version_id=payload.get("instrument_version_id", UNCHANGED),
        assessor_id=payload.get("assessor_id", UNCHANGED),
        brief_ids=payload.get("brief_ids", UNCHANGED),
    )
