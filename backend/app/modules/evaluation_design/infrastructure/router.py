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
    SqlAlchemyRubricRepository,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/instruments", tags=["evaluation-design"])
# The norm-side vocabulary, read-only. Its own prefix: `/admin/instruments/...` would
# collide with the `/{instrument_version_id}` path parameter.
reference_router = APIRouter(prefix="/admin/reference", tags=["evaluation-design"])

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


class ReferenceInstrumentResponse(BaseModel):
    """One version a campaign may pin. A summary, not the instrument (ADR-0056 §4)."""

    rubric_version_id: str
    rubric_id: str
    version: str
    name: str
    scope: str | None
    scale_min: int
    scale_max: int
    # `numeric | likert` — what the points of the scale mean (ADR-0052 §3).
    response_format: str
    criterion_count: int


@reference_router.get("/instruments", response_model=list[ReferenceInstrumentResponse])
def list_reference_instruments(admin: AdminAssessor, uow: Uow) -> list[ReferenceInstrumentResponse]:
    """The human reference instrument's published versions — what a campaign may pin.

    Not `/admin/instruments`: that path serves the automated evidential argument, and the two
    are different artifacts under a shared word (ADR-0056 §3). Only published versions are
    listed, because `open_campaign` refuses any other and an option that cannot work is worse
    than no option.
    """
    summaries = queries.list_published_rubrics(SqlAlchemyRubricRepository(uow.session))
    return [ReferenceInstrumentResponse(**s.__dict__) for s in summaries]


class QualityReferenceResponse(BaseModel):
    quality_id: str
    # Null for a quality that groups under no dimension — it rolls up nowhere.
    dimension_id: str | None


@reference_router.get("/qualities", response_model=list[QualityReferenceResponse])
def list_quality_reference(admin: AdminAssessor, uow: Uow) -> list[QualityReferenceResponse]:
    """The pedagogical vocabulary's grouping (quality → dimension), as it is today.

    What the calibration page's local fitness projection groups by. LIVE reference data on
    purpose: a dry run reads the current vocabulary; the map frozen per instrument version
    at publish (ADR-0023) exists to protect *published studies*, and a preview is neither."""
    mapping = SqlAlchemyReferenceDataRepository(uow.session).quality_dimensions()
    return [
        QualityReferenceResponse(quality_id=quality_id, dimension_id=dimension_id)
        for quality_id, dimension_id in sorted(mapping.items())
    ]
