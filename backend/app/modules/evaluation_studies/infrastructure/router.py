"""Admin HTTP adapter for Evaluation Studies (13-code §3.6/§6).

Translates request/response ↔ use case input/output; domain entities never cross this
boundary. The matching endpoint mounts under `/admin/instruments` (13-code §6 places the
URL with the instrument) while the code stays here, in the operational consumer.
"""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.evaluation_studies.application import (
    criterion_outcomes,
    fitness,
    gathering,
    queries,
    report,
)
from app.modules.evaluation_studies.application.draft import (
    UNCHANGED,
    AssessorHasNotRatified,
    DeclareStudy,
    DeclareStudyCommand,
    InstrumentNotPublished,
    InstrumentRequiredFirst,
    NullNotAllowed,
    UnknownBrief,
    UnknownInstrument,
    UpdateStudyDraft,
    UpdateStudyDraftCommand,
    selection_from,
)
from app.modules.evaluation_studies.application.dtos import StudyDTO
from app.modules.evaluation_studies.application.open_study import OpenStudy, OpenStudyCommand
from app.modules.evaluation_studies.application.sign_off_study import (
    SignOffStudy,
    SignOffStudyCommand,
)
from app.modules.evaluation_studies.domain.model import (
    AssessorNotChosen,
    DatasetEmpty,
    DatasetLocked,
    InstrumentNotChosen,
    InvalidStudy,
    StudyAlreadyOpen,
    StudyAlreadySignedOff,
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

# The three parts of a selection, so both endpoints hand the use case exactly the keys the
# caller sent and nothing else.
_SELECTION_KEYS = frozenset({"instrument_version_id", "assessor_id", "brief_ids"})


class DeclareStudyRequest(BaseModel):
    """A study can be created empty or complete — the console does the latter, in one form.

    Every part of the selection is optional here and replaceable afterwards: none of it is
    binding until the study opens (ADR-0043 §1).
    """

    name: str
    description: str | None = None
    instrument_version_id: str | None = None
    assessor_id: UUID | None = None
    brief_ids: list[UUID] | None = None


class UpdateStudyDraftRequest(BaseModel):
    """A partial update, where absent and null mean different things.

    Sending `assessor_id: null` CLEARS the judge; omitting the key leaves it alone. The
    difference is read from `model_fields_set`, which is the only place pydantic keeps it,
    and it matters because re-pointing a draft at another norm is exactly the moment a
    judge has to be dropped.
    """

    name: str | None = None
    description: str | None = None
    instrument_version_id: str | None = None
    assessor_id: UUID | None = None
    brief_ids: list[UUID] | None = None


class StudyResponse(BaseModel):
    study_id: UUID
    name: str
    description: str | None
    status: str
    instrument_version_id: str | None
    # The id alone: what an assessor is called belongs to Identity, and the console already
    # holds a list of packages keyed by it. Null on studies declared before ADR-0042.
    assessor_id: UUID | None
    brief_ids: list[UUID]
    content_ids: list[UUID]
    created_at: str | None
    opened_at: str | None
    signed_off_at: str | None

    @classmethod
    def from_dto(cls, dto: StudyDTO) -> "StudyResponse":
        return cls(
            study_id=dto.study_id,
            name=dto.name,
            description=dto.description,
            status=dto.status,
            instrument_version_id=dto.instrument_version_id,
            assessor_id=dto.assessor_id,
            brief_ids=list(dto.brief_ids),
            content_ids=list(dto.content_ids),
            created_at=dto.created_at.isoformat() if dto.created_at else None,
            opened_at=dto.opened_at.isoformat() if dto.opened_at else None,
            signed_off_at=dto.signed_off_at.isoformat() if dto.signed_off_at else None,
        )


class StudyReportResponse(BaseModel):
    study_id: UUID
    report: dict[str, Any]
    signed_off_at: str


def _study_response(uow: UnitOfWork, study_id: UUID) -> StudyResponse:
    dto = queries.get_study(SqlAlchemyStudyRepository(uow.session), study_id)
    if dto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")
    return StudyResponse.from_dto(dto)


# What a bad selection maps to, in one place: both endpoints refuse the same things for the
# same reasons, and a reader comparing them should not have to diff two except blocks.
_CONFLICT = (DatasetLocked, StudyAlreadySignedOff)
_UNPROCESSABLE = (
    InvalidStudy,
    NullNotAllowed,
    UnknownInstrument,
    InstrumentNotPublished,
    InstrumentRequiredFirst,
    AssessorHasNotRatified,
    UnknownBrief,
)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StudyResponse)
def declare_study(request: DeclareStudyRequest, admin: AdminAssessor, uow: Uow) -> StudyResponse:
    use_case = DeclareStudy(
        studies=SqlAlchemyStudyRepository(uow.session),
        registry=RegistryGateway(uow.session),
        design=DesignGateway(uow.session),
        evaluation=EvaluationGateway(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        study = use_case(
            DeclareStudyCommand(
                name=request.name,
                description=request.description,
                selection=selection_from(
                    request.model_dump(include=set(_SELECTION_KEYS & request.model_fields_set))
                ),
            )
        )
    except _UNPROCESSABLE as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study.id)


@router.patch("/{study_id}", response_model=StudyResponse)
def update_study_draft(
    study_id: UUID, request: UpdateStudyDraftRequest, admin: AdminAssessor, uow: Uow
) -> StudyResponse:
    """Change any part of a draft. 409 once the study is open — that is where the pin is.

    Only the keys actually sent are applied, so a form that edits one field does not have
    to echo the rest back and cannot clear something by omission.
    """
    use_case = UpdateStudyDraft(
        studies=SqlAlchemyStudyRepository(uow.session),
        registry=RegistryGateway(uow.session),
        design=DesignGateway(uow.session),
        evaluation=EvaluationGateway(uow.session),
        uow=uow,
    )
    sent = request.model_fields_set
    try:
        use_case(
            UpdateStudyDraftCommand(
                study_id=study_id,
                # Forwarded as sent, `null` included: refusing it is the application's rule
                # (a study is read by its name), and answering 422 beats ignoring the key.
                name=request.name if "name" in sent else UNCHANGED,
                description=request.description if "description" in sent else UNCHANGED,
                selection=selection_from(request.model_dump(include=set(_SELECTION_KEYS & sent))),
            )
        )
    except StudyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except _CONFLICT as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except _UNPROCESSABLE as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study_id)


@router.get("", response_model=list[StudyResponse])
def list_studies(admin: AdminAssessor, uow: Uow) -> list[StudyResponse]:
    dtos = queries.list_studies(SqlAlchemyStudyRepository(uow.session))
    return [StudyResponse.from_dto(d) for d in dtos]


@router.get("/{study_id}", response_model=StudyResponse)
def get_study(study_id: UUID, admin: AdminAssessor, uow: Uow) -> StudyResponse:
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
    except (StudyAlreadyOpen, StudyAlreadySignedOff) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (InstrumentNotChosen, AssessorNotChosen, DatasetEmpty) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _study_response(uow, study_id)


@router.post("/{study_id}/sign-off", response_model=StudyResponse)
def sign_off_study(study_id: UUID, admin: AdminAssessor, uow: Uow) -> StudyResponse:
    """The human act that freezes the report — and names who takes responsibility for it.

    The document was readable before this (ADR-0041); what the act adds is the signature.
    """
    use_case = SignOffStudy(
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
        use_case(SignOffStudyCommand(study_id=study_id, signed_off_by=admin.assessor_id))
    except StudyNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (StudyAlreadySignedOff, StudyNotOpen) as exc:
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
            status_code=status.HTTP_404_NOT_FOUND, detail="the study has no signed-off report"
        )
    return StudyReportResponse(
        study_id=dto.study_id,
        report=dto.report,
        signed_off_at=dto.signed_off_at.isoformat(),
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


@router.get("/{study_id}/fitness")
def get_fitness(study_id: UUID, admin: AdminAssessor, uow: Uow) -> dict[str, Any]:
    """The fitness projection (ADR-0023) — an optimization signal, never a judgment.

    Its own resource on purpose: it must not travel inside the study report, whose jsonb is
    frozen when the study is signed off and whose coverage figures use a different
    denominator. Composed on read like the report, and answering at any status — a study
    with nothing pinned gets the same shape with its gaps named, the way readiness informs
    rather than blocks.
    """
    study = SqlAlchemyStudyRepository(uow.session).get_by_id(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")

    instrument_version_id = study.instrument_version_id
    design = DesignGateway(uow.session)
    instrument = design.get_instrument(instrument_version_id) if instrument_version_id else None
    registry = RegistryGateway(uow.session)
    contents = registry.get_contents_by_ids(list(study.content_ids))
    # The recipe as well as what the contents reference (ADR-0039 §3): a commission that
    # produced no course is a reading, not an absence.
    briefs = {
        brief_id: brief
        for brief_id in set(study.brief_ids)
        | {c.brief_id for c in contents if c.brief_id is not None}
        if (brief := registry.get_brief(brief_id)) is not None
    }
    generators = {
        content.generator_version_id: generator
        for content in contents
        if content.generator_version_id
        and (generator := registry.get_generator(content.generator_version_id))
    }
    evaluation = EvaluationGateway(uow.session)
    content_ids = [content.content_id for content in contents]
    judgments = (
        evaluation.get_judgments(content_ids, instrument_version_id, study.assessor_id)
        if instrument_version_id
        else []
    )
    outcomes = (
        evaluation.get_criterion_outcomes(content_ids, instrument_version_id, study.assessor_id)
        if instrument_version_id
        else []
    )
    ratifications = (
        evaluation.list_ratifications(instrument_version_id) if instrument_version_id else []
    )
    return fitness.compute_fitness(
        study=study,
        instrument=instrument,
        contents=contents,
        briefs=briefs,
        generators=generators,
        judgments=judgments,
        outcomes=outcomes,
        ratifications=ratifications,
        computed_at=datetime.now(UTC),
    )


@router.get("/{study_id}/report/preview")
def get_report_preview(study_id: UUID, admin: AdminAssessor, uow: Uow) -> dict[str, Any]:
    """What signing off would write, composed on read — so nobody signs blind.

    Its own resource, and deliberately not a mode of `/report`: that route serves the
    FROZEN row and keeps answering 404 until the human act happens, because the whole
    meaning of a study report is that somebody signed it off. This is the same
    `compose_report` over today's inputs — the same function, so what you read here is what
    signing off writes — minus the one field a preview must not carry: `signedOffAt` filled
    with the composition's clock reads "Signed off now" about a study nobody signed.

    It answers at every status with its gaps named, the way readiness informs rather than
    blocks, and it writes nothing: no event, no row, no commit. The use case that signs off
    is not built here at all.
    """
    study = SqlAlchemyStudyRepository(uow.session).get_by_id(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")

    inputs = gathering.gather_report_inputs(
        study,
        RegistryGateway(uow.session),
        EvaluationGateway(uow.session),
        DesignGateway(uow.session),
        ProfilingGateway(uow.session),
    )
    return report.compose_preview(
        study=study,
        contents=inputs.contents,
        briefs=inputs.briefs,
        generators=inputs.generators,
        judgments=inputs.judgments,
        findings=inputs.findings,
        capabilities=inputs.capabilities,
        instrument=inputs.instrument,
        composed_at=datetime.now(UTC),
    )


@router.get("/{study_id}/criterion-outcomes")
def get_criterion_outcomes(study_id: UUID, admin: AdminAssessor, uow: Uow) -> dict[str, Any]:
    """The per-criterion record across the dataset — what the report structurally cannot say.

    Its own resource for two reasons, both about evidence. The report carries evidence only
    for FAILURES: findings are minted one per failing criterion, so the quote grounding a
    pass — persisted for every pass, guaranteed by a CHECK constraint — is readable
    nowhere. And "which check fails most across these twenty courses" needs a denominator,
    which counting findings cannot give (ADR-0011). Nothing here is aggregated across
    criteria: every distribution travels with its own coverage and stops there.

    A signed-off study answers with the judgments its frozen report recorded rather than
    with today's most recent — re-evaluating a course afterwards must not silently rewrite
    what that report reflects. The payload says which of the two you are reading.
    """
    study = SqlAlchemyStudyRepository(uow.session).get_by_id(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")

    version_id = study.instrument_version_id
    instrument = DesignGateway(uow.session).get_instrument(version_id) if version_id else None
    contents = RegistryGateway(uow.session).get_contents_by_ids(list(study.content_ids))
    content_ids = [content.content_id for content in contents]
    evaluation = EvaluationGateway(uow.session)
    frozen = queries.get_report(SqlAlchemyStudyReportRepository(uow.session), study_id)
    return criterion_outcomes.compute_criterion_outcomes(
        study=study,
        instrument=instrument,
        contents=contents,
        judgments=(
            evaluation.get_judgments(content_ids, version_id, study.assessor_id)
            if version_id
            else []
        ),
        outcomes=(
            evaluation.get_criterion_outcomes(content_ids, version_id, study.assessor_id)
            if version_id
            else []
        ),
        frozen_report=frozen.report if frozen is not None else None,
        computed_at=datetime.now(UTC),
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
