"""The slice end to end (13-code §10): register → profile → publish → ratify → evaluate →
declare/pin/compose/open/publish → report with coverage and caveats.

Two registrations of the frozen `introduction-to-generative-ai` package carry the same
syllabus, so the brief intake (ADR-0022) pairs them automatically — one linked to a
generator version, one left unknown. The report must count only the linked one at
generator level, name the other in the caveat, and surface the real numbering-drift
finding ('05'/'06') with its quote.
"""

import pytest
from sqlalchemy import text
from test_automated_evaluation_flow import (
    COURSE,
    copy_spec,
    publish_instrument,
    track_automated,
)
from test_content_profiling_commands import profile_content_use_case

import app.main  # noqa: F401 — wires the judgment policy into the global dispatcher
from app.cli import DEMO_PACKAGES_DIR, _demo_artifacts, run_evaluate, run_ratify_assessor
from app.modules.content_profiling.application.profile_content import ProfileContentCommand
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.application.register_generator_version import (
    RegisterGeneratorVersion,
    RegisterGeneratorVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.brief_intake import LearnpackBriefIntake
from app.modules.evaluand_registry.infrastructure.fetchers import FilesystemArtifactFetcher
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.modules.evaluation_studies.application.compose_dataset import (
    ComposeDataset,
    ComposeDatasetCommand,
)
from app.modules.evaluation_studies.application.declare_study import (
    DeclareStudy,
    DeclareStudyCommand,
)
from app.modules.evaluation_studies.application.open_study import OpenStudy, OpenStudyCommand
from app.modules.evaluation_studies.application.pin_instrument import (
    PinInstrument,
    PinInstrumentCommand,
)
from app.modules.evaluation_studies.application.publish_study import (
    PublishStudy,
    PublishStudyCommand,
)
from app.modules.evaluation_studies.domain.model import StudyAlreadyPublished
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
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork


@pytest.fixture
def admin(register_assessor, unique):
    email = f"admin-{unique}@example.com"
    assessor_id = register_assessor(f"user_admin_{unique}", email, "Admin")
    return assessor_id, email


@pytest.fixture
def patched_package(unique, monkeypatch):
    """The structural package, cloned onto the throwaway lineage (same coverage)."""
    import dataclasses

    from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS

    base = AUTOMATED_ASSESSORS[("structural", "1")]
    name = f"structural-{unique}"
    lineage = f"qa-copy-{unique}"
    package = dataclasses.replace(
        base,
        name=name,
        instrument_id=lineage,
        source_config={**base.source_config, "name": name, "instrumentId": lineage},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, base.version), package)
    return package


def _register_course(cleanup, unique, suffix, generator_version_id=None):
    """The frozen intro course, registered with its real artifacts — syllabus included,
    so the intake derives the brief."""
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        content = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
            brief_intake=LearnpackBriefIntake(FilesystemArtifactFetcher(DEMO_PACKAGES_DIR)),
        )(
            RegisterContentVersionCommand(
                package_format="LearnpackV1",
                external_id=f"study-flow-{suffix}-{unique}",
                consumable_url=f"https://study-flow-{suffix}-{unique}.learn-pack.com/",
                artifacts=_demo_artifacts(COURSE),
                generator_version_id=generator_version_id,
            )
        )
    cleanup["contents"].append(content.id)
    if content.brief_id and content.brief_id not in cleanup["briefs"]:
        cleanup["briefs"].append(content.brief_id)
    with SessionLocal() as session:
        profile_content_use_case(session)(ProfileContentCommand(content_id=content.id))
    return content


def _register_generator(cleanup, unique):
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        generator = RegisterGeneratorVersion(
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(RegisterGeneratorVersionCommand(name=f"studies-flow-generator-{unique}", version="1.0.0"))
    cleanup["generators"].append(generator.id)
    return generator.id


def _studies_wiring(session):
    uow = UnitOfWork(session)
    return uow, SqlAlchemyStudyRepository(session)


def test_the_first_increment_closes_the_loop(
    cleanup, unique, session, namespace, admin, patched_package
):
    admin_id, email = admin

    # --- the evaluand side: paired registrations, one generator known, one unknown
    generator_id = _register_generator(cleanup, unique)
    linked = _register_course(cleanup, unique, "linked", generator_version_id=generator_id)
    orphan = _register_course(cleanup, unique, "orphan")
    assert linked.brief_id == orphan.brief_id  # ADR-0022: hash identity pairs them
    brief_id = linked.brief_id

    # --- the norm: a published copy of the real instrument, ratified for the assessor
    version_id = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", version_id, email, []) == 0
    track_automated(cleanup, patched_package.name)

    # --- the judgments
    assessor_arg = f"{patched_package.name}:1"
    assert run_evaluate(str(linked.id), version_id, assessor_arg, False) == 0
    assert run_evaluate(str(orphan.id), version_id, assessor_arg, False) == 0

    # --- the study lifecycle
    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        study = DeclareStudy(studies, uow.events, uow)(
            DeclareStudyCommand(purpose=f"First paired round ({unique})")
        )
    cleanup["studies"].append(study.id)

    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        PinInstrument(studies, DesignGateway(s), uow.events, uow)(
            PinInstrumentCommand(study_id=study.id, instrument_version_id=version_id)
        )
    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        composed = ComposeDataset(studies, RegistryGateway(s), uow)(
            ComposeDatasetCommand(study_id=study.id, brief_ids=[brief_id])
        )
    assert set(composed.content_ids) == {linked.id, orphan.id}  # the recipe resolved both

    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        OpenStudy(studies, uow.events, uow)(OpenStudyCommand(study_id=study.id))

    def publish():
        with SessionLocal() as s:
            uow, studies = _studies_wiring(s)
            return PublishStudy(
                studies=studies,
                reports=SqlAlchemyStudyReportRepository(s),
                registry=RegistryGateway(s),
                evaluation=EvaluationGateway(s),
                design=DesignGateway(s),
                profiling=ProfilingGateway(s),
                publisher=uow.events,
                uow=uow,
            )(PublishStudyCommand(study_id=study.id, published_by=admin_id))

    publish()

    # --- the report
    report = SqlAlchemyStudyReportRepository(session).get(study.id).report

    judgment_rows = {
        str(row["content_id"]): str(row["id"])
        for row in session.execute(
            text(
                "SELECT id, content_id FROM quality_judgments "
                "WHERE content_id = ANY(:ids) AND instrument_version_id = :v"
            ),
            {"ids": [linked.id, orphan.id], "v": version_id},
        ).mappings()
    }
    assert report["judgmentIdsUsed"] == judgment_rows  # exactly the persisted judgments

    sections = {c["contentId"]: c for c in report["contents"]}
    assert set(sections) == {str(linked.id), str(orphan.id)}
    for section in sections.values():
        assert section["briefId"] == str(brief_id)
        assert section["claims"]  # judged, with evidence basis per claim
        assert all("evidenceBasis" in claim for claim in section["claims"])

    # The real numbering drift ('05'/'06') survives all the way into the report.
    drift = [
        f
        for f in sections[str(linked.id)]["findings"]
        if f["criterionId"] == "cr-module-structure-well-formed"
    ]
    assert drift and drift[0]["quote"]

    # Generator level counts only the linked content; the orphan is a named exclusion.
    assert len(report["generatorLevel"]) == 1
    generator_section = report["generatorLevel"][0]
    assert generator_section["generatorVersionId"] == str(generator_id)
    assert generator_section["contentsCounted"] == 1
    for per_claim in generator_section["perClaim"]:
        assert per_claim["coverage"]["of"] == 1  # coverage alongside, ADR-0011

    caveats = report["caveats"]
    assert caveats["unknownExclusions"]["contentIds"] == [str(orphan.id)]
    assert caveats["unresolvedDisagreements"] == []  # inert but present
    assert caveats["briefCompleteness"] == [
        {"briefId": str(brief_id), "promptRecorded": False, "origin": "ai_derived_syllabus"}
    ]
    # structural:1 abstains from the judgment criteria (ADR-0018): those claims are
    # insufficient with their cause named, never silent.
    insufficient = caveats["insufficientEvidence"]
    assert insufficient and all(
        c["cause"] in {"not_assessed", "no_evidence", "mixed"} for c in insufficient
    )

    # --- the outbox trail
    event_types = {
        row[0]
        for row in session.execute(
            text("SELECT event_type FROM events WHERE aggregate_id = :id"),
            {"id": str(study.id)},
        )
    }
    assert event_types == {"StudyDeclared", "InstrumentPinned", "StudyOpened", "StudyPublished"}

    # --- published means immutable, in the domain and in the row
    with pytest.raises(StudyAlreadyPublished):
        publish()
    unchanged = SqlAlchemyStudyReportRepository(session).get(study.id).report
    assert unchanged == report
