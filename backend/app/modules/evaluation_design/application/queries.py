"""Read-only queries of Evaluation Design (11-connect §published language).

`get_instrument(version) → InstrumentSnapshot` is how Evaluation and Studies read an
instrument — self-contained, never by touching the tables. `get_rubric` is the legacy
surface for the human reference instrument (ADR-0015, ADR-0052).
"""

from app.modules.evaluation_design.application.dtos import (
    BindingDTO,
    ClaimDTO,
    CriterionSpecDTO,
    DataRequirementDTO,
    InstrumentSnapshot,
    RubricSnapshot,
)
from app.modules.evaluation_design.application.ports import (
    DataRequirementRepositoryPort,
    InstrumentRepositoryPort,
    RubricRepositoryPort,
)
from app.modules.evaluation_design.domain.instrument import InstrumentVersion


def get_rubric(rubrics: RubricRepositoryPort, rubric_version_id: str) -> RubricSnapshot | None:
    return rubrics.get_snapshot(rubric_version_id)


def _to_snapshot(instrument: InstrumentVersion) -> InstrumentSnapshot:
    return InstrumentSnapshot(
        instrument_version_id=instrument.id,
        instrument_id=instrument.instrument_id,
        version=instrument.version,
        name=instrument.name,
        purpose=instrument.purpose,
        status=instrument.status,
        claims=[
            ClaimDTO(
                claim_id=c.claim_id,
                statement=c.statement,
                quality_ids=list(c.quality_ids),
                warrants=list(c.warrants),
                alternative_explanations=list(c.alternative_explanations),
                sufficiency_rule=c.sufficiency.rule,
            )
            for c in instrument.claims
        ],
        criteria=[
            CriterionSpecDTO(
                criterion_id=c.criterion_id,
                statement=c.statement,
                pass_condition=c.pass_condition,
                failure_modes=list(c.failure_modes),
                claim_ids=list(c.claim_ids),
                required_data=list(c.required_data),
                on_missing_evidence=c.on_missing_evidence,
                eligible_sources=list(c.eligible_sources),
                condition=c.condition,
            )
            for c in instrument.criteria
        ],
        bindings=[
            BindingDTO(package_format=b.package_format, task_variables=b.task_variables)
            for b in instrument.bindings
        ],
        quality_dimensions=dict(instrument.quality_dimensions),
    )


def get_instrument(
    instruments: InstrumentRepositoryPort, instrument_version_id: str
) -> InstrumentSnapshot | None:
    instrument = instruments.get(instrument_version_id)
    return None if instrument is None else _to_snapshot(instrument)


def list_instruments(instruments: InstrumentRepositoryPort) -> list[InstrumentSnapshot]:
    return [_to_snapshot(i) for i in instruments.list_all()]


def get_data_requirements(
    data_requirements: DataRequirementRepositoryPort,
) -> list[DataRequirementDTO]:
    """The generated view of the namespace (ADR-0014 — never a curated artifact)."""
    return [
        DataRequirementDTO(
            id=r.id,
            definition=r.definition,
            aliases=list(r.aliases),
            value_domain=r.value_domain,
            grounded_in=list(r.grounded_in),
        )
        for r in sorted(data_requirements.get_all().values(), key=lambda r: r.id)
    ]
