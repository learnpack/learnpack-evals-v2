"""Admin HTTP adapter for Evaluation Design.

Read-only surface plus the one write that must be a human act: publishing (design 12,
invariant 4/5). Authoring itself stays file-based (`app.cli import-instrument`) — there is
no authoring UI in the first increment.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.evaluation_design.application import queries
from app.modules.evaluation_design.application.dtos import InstrumentSnapshot
from app.modules.evaluation_design.application.publish_instrument import (
    InstrumentNotFound,
    PublishInstrument,
    PublishInstrumentCommand,
)
from app.modules.evaluation_design.domain.instrument import InstrumentImmutable, InvalidInstrument
from app.modules.evaluation_design.infrastructure.repository import (
    SqlAlchemyDataRequirementRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemyReferenceDataRepository,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/instruments", tags=["evaluation-design"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class ClaimResponse(BaseModel):
    claim_id: str
    statement: str
    quality_ids: list[str]
    warrants: list[str]
    alternative_explanations: list[str]
    sufficiency_rule: str


class CriterionSpecResponse(BaseModel):
    criterion_id: str
    statement: str | None
    pass_condition: str
    failure_modes: list[str]
    claim_ids: list[str]
    required_data: list[str]
    on_missing_evidence: str
    eligible_sources: list[str]
    condition: dict[str, Any] | None


class BindingResponse(BaseModel):
    package_format: str
    task_variables: dict[str, Any]


class InstrumentResponse(BaseModel):
    instrument_version_id: str
    instrument_id: str
    version: str
    name: str
    purpose: str
    status: str
    claims: list[ClaimResponse]
    criteria: list[CriterionSpecResponse]
    bindings: list[BindingResponse]

    @classmethod
    def from_snapshot(cls, snapshot: InstrumentSnapshot) -> "InstrumentResponse":
        return cls(
            instrument_version_id=snapshot.instrument_version_id,
            instrument_id=snapshot.instrument_id,
            version=snapshot.version,
            name=snapshot.name,
            purpose=snapshot.purpose,
            status=snapshot.status,
            claims=[ClaimResponse(**c.__dict__) for c in snapshot.claims],
            criteria=[CriterionSpecResponse(**c.__dict__) for c in snapshot.criteria],
            bindings=[BindingResponse(**b.__dict__) for b in snapshot.bindings],
        )


@router.get("", response_model=list[InstrumentResponse])
def list_instruments(admin: AdminAssessor, uow: Uow) -> list[InstrumentResponse]:
    snapshots = queries.list_instruments(SqlAlchemyInstrumentRepository(uow.session))
    return [InstrumentResponse.from_snapshot(s) for s in snapshots]


@router.get("/{instrument_version_id}", response_model=InstrumentResponse)
def get_instrument(
    instrument_version_id: str, admin: AdminAssessor, uow: Uow
) -> InstrumentResponse:
    snapshot = queries.get_instrument(
        SqlAlchemyInstrumentRepository(uow.session), instrument_version_id
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="instrument not found")
    return InstrumentResponse.from_snapshot(snapshot)


@router.post("/{instrument_version_id}/publish", response_model=InstrumentResponse)
def publish_instrument(
    instrument_version_id: str, admin: AdminAssessor, uow: Uow
) -> InstrumentResponse:
    use_case = PublishInstrument(
        instruments=SqlAlchemyInstrumentRepository(uow.session),
        data_requirements=SqlAlchemyDataRequirementRepository(uow.session),
        reference=SqlAlchemyReferenceDataRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        use_case(
            PublishInstrumentCommand(
                instrument_version_id=instrument_version_id,
                published_by=admin.assessor_id,
            )
        )
    except InstrumentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instrument not found"
        ) from exc
    except InstrumentImmutable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidInstrument as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    snapshot = queries.get_instrument(
        SqlAlchemyInstrumentRepository(uow.session), instrument_version_id
    )
    assert snapshot is not None  # just published in this transaction
    return InstrumentResponse.from_snapshot(snapshot)
