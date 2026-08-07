"""Admin HTTP adapter for Evaluation Studies (13-code §3.6/§6).

Translates request/response ↔ use case input/output; domain entities never cross this
boundary. The matching endpoint mounts under `/admin/instruments` (13-code §6 places the
URL with the instrument) while the code stays here, in the operational consumer.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.evaluation_studies.application import queries
from app.modules.evaluation_studies.application.compose_dataset import (
    ComposeDataset,
    ComposeDatasetCommand,
    UnknownBrief,
)
from app.modules.evaluation_studies.application.declare_study import (
    DeclareStudy,
    DeclareStudyCommand,
)
from app.modules.evaluation_studies.application.dtos import StudyDTO
from app.modules.evaluation_studies.application.open_study import OpenStudy, OpenStudyCommand
from app.modules.evaluation_studies.application.pin_instrument import (
    InstrumentNotPublished,
    PinInstrument,
    PinInstrumentCommand,
    UnknownInstrument,
)
from app.modules.evaluation_studies.application.publish_study import (
    PublishStudy,
    PublishStudyCommand,
)
from app.modules.evaluation_studies.domain.model import (
    DatasetEmpty,
    DatasetLocked,
    InstrumentAlreadyPinned,
    InstrumentNotPinned,
    InvalidStudy,
    StudyAlreadyOpen,
    StudyAlreadyPublished,
    StudyNotFound,
    StudyNotOpen,
)
from app.modules.evaluation_studies.infrastructure.gateways import (
    DesignGateway,
    EvaluationGateway,
    ProfilingGateway,
    RegistryGateway,
)
from app.modules.evaluation_studies.infrastructure.repository import (
    SqlAlchemyStudyReportRepository,
    SqlAlchemyStudyRepository,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/studies", tags=["evaluation-studies"])
instruments_router = APIRouter(prefix="/admin/instruments", tags=["evaluation-studies"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class DeclareStudyRequest(BaseModel):
    purpose: str


class PinInstrumentRequest(BaseModel):
    instrument_version_id: str


class ComposeDatasetRequest(BaseModel):
    brief_ids: list[UUID]


class StudyResponse(BaseModel):
    study_id: UUID
    purpose: str
    status: str
    instrument_version_id: str | None
    brief_ids: list[UUID]
    content_ids: list[UUID]
    created_at: str | None
    opened_at: str | None
    published_at: str | None

    @classmethod
    def from_dto(cls, dto: StudyDTO) -> "StudyResponse":
        return cls(
            study_id=dto.study_id,
            purpose=dto.purpose,
            status=dto.status,
            instrument_version_id=dto.instrument_version_id,
            brief_ids=list(dto.brief_ids),
            content_ids=list(dto.content_ids),
            created_at=dto.created_at.isoformat() if dto.created_at else None,
            opened_at=dto.opened_at.isoformat() if dto.opened_at else None,
            published_at=dto.published_at.isoformat() if dto.published_at else None,
        )


class StudyReportResponse(BaseModel):
    study_id: UUID
    report: dict[str, Any]
    published_at: str


def _study_response(uow: UnitOfWork, study_id: UUID) -> StudyResponse:
    dto = queries.get_study(SqlAlchemyStudyRepository(uow.session), study_id)
    if dto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")
    return StudyResponse.from_dto(dto)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StudyResponse)
def declare_study(request: DeclareStudyRequest, admin: AdminAssessor, uow: Uow) -> StudyResponse:
    use_case = DeclareStudy(
        studies=SqlAlchemyStudyRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        study = use_case(DeclareStudyCommand(purpose=request.purpose))
    except InvalidStudy as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study.id)


@router.get("", response_model=list[StudyResponse])
def list_studies(admin: AdminAssessor, uow: Uow) -> list[StudyResponse]:
    dtos = queries.list_studies(SqlAlchemyStudyRepository(uow.session))
    return [StudyResponse.from_dto(d) for d in dtos]


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(study_id: UUID, admin: AdminAssessor, uow: Uow) -> StudyResponse:
    return _study_response(uow, study_id)


@router.post("/{study_id}/pin", response_model=StudyResponse)
def pin_instrument(
    study_id: UUID, request: PinInstrumentRequest, admin: AdminAssessor, uow: Uow
) -> StudyResponse:
    use_case = PinInstrument(
        studies=SqlAlchemyStudyRepository(uow.session),
        instruments=DesignGateway(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        use_case(
            PinInstrumentCommand(
                study_id=study_id, instrument_version_id=request.instrument_version_id
            )
        )
    except StudyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (InstrumentAlreadyPinned, DatasetLocked, StudyAlreadyPublished) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (UnknownInstrument, InstrumentNotPublished) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study_id)


@router.post("/{study_id}/dataset", response_model=StudyResponse)
def compose_dataset(
    study_id: UUID, request: ComposeDatasetRequest, admin: AdminAssessor, uow: Uow
) -> StudyResponse:
    use_case = ComposeDataset(
        studies=SqlAlchemyStudyRepository(uow.session),
        registry=RegistryGateway(uow.session),
        uow=uow,
    )
    try:
        use_case(ComposeDatasetCommand(study_id=study_id, brief_ids=request.brief_ids))
    except StudyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (DatasetLocked, StudyAlreadyPublished) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnknownBrief as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study_id)


@router.post("/{study_id}/open", response_model=StudyResponse)
def open_study(study_id: UUID, admin: AdminAssessor, uow: Uow) -> StudyResponse:
    use_case = OpenStudy(
        studies=SqlAlchemyStudyRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        use_case(OpenStudyCommand(study_id=study_id))
    except StudyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (StudyAlreadyOpen, StudyAlreadyPublished) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (InstrumentNotPinned, DatasetEmpty) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study_id)


@router.post("/{study_id}/publish", response_model=StudyResponse)
def publish_study(study_id: UUID, admin: AdminAssessor, uow: Uow) -> StudyResponse:
    use_case = PublishStudy(
        studies=SqlAlchemyStudyRepository(uow.session),
        reports=SqlAlchemyStudyReportRepository(uow.session),
        registry=RegistryGateway(uow.session),
        evaluation=EvaluationGateway(uow.session),
        design=DesignGateway(uow.session),
        profiling=ProfilingGateway(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        use_case(PublishStudyCommand(study_id=study_id, published_by=admin.assessor_id))
    except StudyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (StudyAlreadyPublished, StudyNotOpen) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnknownInstrument as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study_id)


@router.get("/{study_id}/report", response_model=StudyReportResponse)
def get_report(study_id: UUID, admin: AdminAssessor, uow: Uow) -> StudyReportResponse:
    dto = queries.get_report(SqlAlchemyStudyReportRepository(uow.session), study_id)
    if dto is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="the study has no published report"
        )
    return StudyReportResponse(
        study_id=dto.study_id,
        report=dto.report,
        published_at=dto.published_at.isoformat(),
    )


@router.get("/{study_id}/readiness")
def get_readiness(study_id: UUID, admin: AdminAssessor, uow: Uow) -> dict[str, Any]:
    """Gaps per claim + study-level gaps. Informs, never blocks (12-define inv. 1)."""
    study = SqlAlchemyStudyRepository(uow.session).get_by_id(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")

    design = DesignGateway(uow.session)
    instrument = (
        design.get_instrument(study.instrument_version_id) if study.instrument_version_id else None
    )
    registry = RegistryGateway(uow.session)
    dataset_formats = [
        c.package_format for c in registry.get_contents_by_ids(list(study.content_ids))
    ]
    profiling = ProfilingGateway(uow.session)
    capabilities = {f: profiling.get_capabilities(f) for f in set(dataset_formats)}
    ratifications = (
        EvaluationGateway(uow.session).list_ratifications(study.instrument_version_id)
        if study.instrument_version_id
        else []
    )
    return queries.compute_readiness(
        study, instrument, capabilities, ratifications, dataset_formats
    )


@instruments_router.get("/{instrument_version_id}/matching")
def get_matching(
    instrument_version_id: str, package_format: str, admin: AdminAssessor, uow: Uow
) -> dict[str, Any]:
    """Demand × supply (13-code §6): expected coverage + unmet demand per format."""
    instrument = DesignGateway(uow.session).get_instrument(instrument_version_id)
    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="instrument version not found"
        )
    capability = ProfilingGateway(uow.session).get_capabilities(package_format)
    return queries.compute_matching(instrument, capability, package_format)
