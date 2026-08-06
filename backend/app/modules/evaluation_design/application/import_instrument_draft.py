"""Use case: import (create or replace) an instrument draft from an authored spec.

The spec arrives as plain data (the YAML is parsed at the edge — CLI). Data
requirements referenced by criteria are minted here, definition included, with the
ADR-0014 lint: an existing id whose definition differs is an error, never a silent
overwrite. `revise_definitions` is the deliberate act that lifts the lint — the
differing definition is applied and reported as a revision (same meaning, better
wording; judging sameness stays human). Draft edits publish no event
(first-increment mark) — the publication event is the contract.
"""

from dataclasses import dataclass, field
from typing import Any

from app.modules.evaluation_design.application.ports import (
    DataRequirementRepositoryPort,
    InstrumentRepositoryPort,
)
from app.modules.evaluation_design.domain.instrument import (
    Claim,
    Criterion,
    InstrumentVersion,
    Sufficiency,
    TaskModelBinding,
)
from app.modules.evaluation_design.domain.reference import DataRequirement
from app.shared.application.ports import UnitOfWorkPort


class InstrumentImportError(Exception):
    """The spec cannot become a valid draft. `problems` lists every issue found."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class ImportInstrumentDraftCommand:
    spec: dict[str, Any]
    revise_definitions: bool = False


@dataclass(frozen=True)
class DefinitionRevision:
    """A definition overwrite the author explicitly asked for (`revise_definitions`)."""

    id: str
    old_definition: str
    new_definition: str


@dataclass(frozen=True)
class ImportResult:
    instrument: InstrumentVersion
    minted_data_requirements: list[str] = field(default_factory=list)
    revised_data_requirements: list[DefinitionRevision] = field(default_factory=list)


class ImportInstrumentDraft:
    def __init__(
        self,
        instruments: InstrumentRepositoryPort,
        data_requirements: DataRequirementRepositoryPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._instruments = instruments
        self._data_requirements = data_requirements
        self._uow = uow

    def __call__(self, command: ImportInstrumentDraftCommand) -> ImportResult:
        spec = command.spec
        instrument = _build_instrument(spec)

        existing = self._instruments.get(instrument.id)
        if existing is not None:
            existing.require_editable()  # published → InstrumentImmutable ("bump the version")

        minted, revised = self._mint_data_requirements(
            spec, instrument, revise_definitions=command.revise_definitions
        )

        self._instruments.save_draft(instrument)
        self._uow.commit()
        return ImportResult(
            instrument=instrument,
            minted_data_requirements=minted,
            revised_data_requirements=revised,
        )

    def _mint_data_requirements(
        self, spec: dict[str, Any], instrument: InstrumentVersion, revise_definitions: bool
    ) -> tuple[list[str], list[DefinitionRevision]]:
        known = self._data_requirements.get_all()
        declared = {
            str(raw["id"]): DataRequirement(
                id=str(raw["id"]),
                definition=str(raw.get("definition", "")),
                aliases=tuple(raw.get("aliases", [])),
                value_domain=raw.get("value_domain"),
                grounded_in=tuple(raw.get("grounded_in", [])),
            )
            for raw in spec.get("data_requirements", [])
        }

        problems: list[str] = []
        revised: list[DefinitionRevision] = []
        # Lint (ADR-0014): same id, different definition — search before minting.
        for requirement in declared.values():
            current = known.get(requirement.id)
            if current is not None and current.definition != requirement.definition:
                if revise_definitions:
                    revised.append(
                        DefinitionRevision(
                            id=requirement.id,
                            old_definition=current.definition,
                            new_definition=requirement.definition,
                        )
                    )
                else:
                    problems.append(
                        f"data requirement '{requirement.id}' already exists with a different "
                        f"definition — same meaning → keep the definition (or add an alias); "
                        f"similar-but-different → mint a new id. "
                        f"existing: '{current.definition}' / imported: '{requirement.definition}'"
                    )
        # Every id a criterion requires must be defined somewhere (file or namespace).
        available = set(known) | set(declared)
        for criterion in instrument.criteria:
            unknown = set(criterion.required_data) - available
            if unknown:
                problems.append(
                    f"criterion {criterion.criterion_id} requires undefined data ids: "
                    f"{', '.join(sorted(unknown))} — declare them under data_requirements "
                    "with a definition (ADR-0014)"
                )
        if problems:
            raise InstrumentImportError(problems)

        minted = [r.id for r in declared.values() if r.id not in known]
        for requirement in declared.values():
            self._data_requirements.upsert(requirement)
        return minted, revised


def _build_instrument(spec: dict[str, Any]) -> InstrumentVersion:
    """Shape validation happens in the domain constructors; KeyErrors become problems."""
    try:
        instrument_id = str(spec["instrument_id"])
        version = str(spec["version"])
        claims = tuple(
            Claim(
                claim_id=str(raw["id"]),
                statement=str(raw["statement"]),
                quality_ids=tuple(raw.get("qualities", [])),
                warrants=tuple(raw.get("warrants", [])),
                alternative_explanations=tuple(raw.get("alternative_explanations", [])),
                sufficiency=Sufficiency(rule=raw.get("sufficiency", {}).get("rule", "conjunctive")),
            )
            for raw in spec.get("claims", [])
        )
        criteria = tuple(
            Criterion(
                criterion_id=str(raw["id"]),
                statement=raw.get("statement"),
                pass_condition=str(raw["pass_condition"]),
                failure_modes=tuple(raw.get("failure_modes", [])),
                claim_ids=tuple(raw.get("claims", [])),
                required_data=tuple(raw.get("requires", [])),
                on_missing_evidence=raw.get("on_missing_evidence", "no_evidence"),
                eligible_sources=tuple(raw.get("eligible_sources", ["human", "automated"])),
                condition=raw.get("condition"),
            )
            for raw in spec.get("criteria", [])
        )
        bindings = tuple(
            TaskModelBinding(
                package_format=str(raw["package_format"]),
                task_variables=raw.get("task_variables", {}),
            )
            for raw in spec.get("bindings", [])
        )
        return InstrumentVersion(
            id=f"{instrument_id}-{version}",
            instrument_id=instrument_id,
            version=version,
            name=str(spec["name"]),
            purpose=str(spec["purpose"]),
            claims=claims,
            criteria=criteria,
            bindings=bindings,
            revision_reason=spec.get("revision_reason"),
            assisted_by=spec.get("assisted_by"),
        )
    except KeyError as exc:
        raise InstrumentImportError([f"missing required field: {exc.args[0]}"]) from exc
