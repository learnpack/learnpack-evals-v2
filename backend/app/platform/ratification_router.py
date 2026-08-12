"""The ratification act over HTTP — the second gate of ADR-0019 (ADR-0036).

It lives in the composition root, not in Evaluation's router, because it spans two
modules: Identity mints the automated assessor's row and owns the refusal when the stored
`source_config` no longer matches the code (ADR-0016 §2), Evaluation decides everything
about coverage and the delta. Wiring two modules' adapters in one transaction is what a
composition root is for, and `platform/` is one — the same standing `cli.py` has, which
composes the very same two use cases behind `ratify-assessor`.

The route belongs to the assessor-package resource all the same; only the file sits
outside either module.

What the gate adds over the use cases is the vocabulary a client can act on: the delta
answers **409** carrying the criteria to decide, one by one, with the `pass_condition`
being confirmed (ADR-0036 §2 and §4) — everything else the act can refuse answers 422 with
its cause named.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.evaluation.application.ratify_assessor import (
    RatificationNeedsConfirmation,
    RatificationRefused,
    RatifyAssessor,
    RatifyAssessorCommand,
)
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation.infrastructure.gateways import DesignInstrumentGateway
from app.modules.evaluation.infrastructure.repository import SqlAlchemyRatificationRepository
from app.modules.identity.application.register_automated_assessor import (
    AutomatedAssessorDrifted,
    RegisterAutomatedAssessor,
    RegisterAutomatedAssessorCommand,
)
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/assessor-packages", tags=["automated-evaluation"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class RatifyAssessorRequest(BaseModel):
    instrument_version_id: str
    # One id per executed criterion whose normative text changed: the decision ADR-0019 §3
    # demands, taken here rather than assumed.
    confirmed: list[str] = []


class RatifyAssessorResponse(BaseModel):
    assessor_id: str
    instrument_version_id: str
    # False when this version was already ratified — the act is idempotent, and saying it
    # did not happen again is not the same as saying nothing is ratified.
    newly_ratified: bool
    # True the first time: the initial registration IS the first ratification (ADR-0019 §2).
    newly_registered: bool


@router.post("/{name}/{version}/ratify", response_model=RatifyAssessorResponse)
def ratify_assessor(
    name: str, version: str, request: RatifyAssessorRequest, admin: AdminAssessor, uow: Uow
) -> RatifyAssessorResponse:
    """Make one instrument version evaluable by one assessor package.

    Deliberate, irreversible and recorded with its author — the console states as much
    before asking (ADR-0036 §5). Everything it refuses, it refuses by name.
    """
    package = AUTOMATED_ASSESSORS.get((name, version))
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown assessor {name}:{version}"
        )

    try:
        registered = RegisterAutomatedAssessor(SqlAlchemyAssessorRepository(uow.session))(
            RegisterAutomatedAssessorCommand(
                name=package.name,
                version=package.version,
                display_name=package.display_name,
                source_config=package.source_config,
            )
        )
    except AutomatedAssessorDrifted as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    use_case = RatifyAssessor(
        instruments=DesignInstrumentGateway(uow.session),
        ratifications=SqlAlchemyRatificationRepository(uow.session),
        uow=uow,
    )
    try:
        result = use_case(
            RatifyAssessorCommand(
                assessor_id=registered.assessor.assessor_id,
                instrument_id=package.instrument_id,
                instrument_version_id=request.instrument_version_id,
                coverage=package.coverage,
                ratified_by=admin.assessor_id,
                confirmed=frozenset(request.confirmed),
            )
        )
    except RatificationNeedsConfirmation as exc:
        # An object, not a sentence: the ids and the texts are what the client has to
        # render and send back, so they are contract (ADR-0031's shape, ADR-0036 §4).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "executed criteria changed since the last ratified version "
                    f"({exc.previous_version_id}): confirm that the executor still realizes "
                    "each text"
                ),
                "previous_version_id": exc.previous_version_id,
                "criteria": [
                    {
                        "criterion_id": delta.criterion_id,
                        "change": delta.change,
                        "pass_condition": delta.pass_condition,
                    }
                    for delta in exc.pending
                ],
            },
        ) from exc
    except RatificationRefused as exc:
        # Unknown version, a draft, a foreign lineage, coverage that leaves a criterion
        # undecided: nothing a retry fixes, and each says which one it was.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return RatifyAssessorResponse(
        assessor_id=str(registered.assessor.assessor_id),
        instrument_version_id=result.instrument_version_id,
        newly_ratified=result.newly_ratified,
        newly_registered=registered.newly_registered,
    )
