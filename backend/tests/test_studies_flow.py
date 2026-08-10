"""The slice end to end (13-code §10): register → profile → publish → ratify → evaluate →
declare/pin/compose/open/publish → report with coverage and caveats.

Two registrations of the frozen `introduction-to-generative-ai` package carry the same
syllabus, so the brief intake (ADR-0022) pairs them automatically — one linked to a
generator version, one left unknown. The report must count only the linked one at
generator level, name the other in the caveat, and surface the real numbering-drift
finding ('05'/'06') with its quote.
"""

from datetime import UTC, datetime

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
from app.cli import (
    DEMO_PACKAGES_DIR,
    run_attribute_generator,
    run_evaluate,
    run_ratify_assessor,
)
from app.modules.content_profiling.application.profile_content import ProfileContentCommand
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.brief_intake import PackageBriefIntake
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
from app.modules.evaluation_studies.application.fitness import compute_fitness
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
from app.shared.infrastructure.fetchers import FilesystemFetcher
from tests.conftest import fixture_artifact_rows


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
            brief_intake=PackageBriefIntake(FilesystemFetcher(DEMO_PACKAGES_DIR)),
        )(
            RegisterContentVersionCommand(
                package_format="LearnpackV1",
                external_id=f"study-flow-{suffix}-{unique}",
                consumable_url=f"https://study-flow-{suffix}-{unique}.learn-pack.com/",
                artifacts=fixture_artifact_rows(COURSE),
                generator_version_id=generator_version_id,
            )
        )
    cleanup["contents"].append(content.id)
    if content.brief_id and content.brief_id not in cleanup["briefs"]:
        cleanup["briefs"].append(content.brief_id)
    with SessionLocal() as session:
        profile_content_use_case(session)(ProfileContentCommand(content_id=content.id))
    return content


def _studies_wiring(session):
    uow = UnitOfWork(session)
    return uow, SqlAlchemyStudyRepository(session)


def _project_fitness(session, study_id):
    """The fitness read, composed from the same gateways the endpoint and the CLI use."""
    study = SqlAlchemyStudyRepository(session).get_by_id(study_id)
    registry, evaluation = RegistryGateway(session), EvaluationGateway(session)
    contents = registry.get_contents_by_ids(list(study.content_ids))
    content_ids = [c.content_id for c in contents]
    version_id = study.instrument_version_id
    return compute_fitness(
        study=study,
        instrument=DesignGateway(session).get_instrument(version_id),
        contents=contents,
        generators={
            c.generator_version_id: generator
            for c in contents
            if c.generator_version_id
            and (generator := registry.get_generator(c.generator_version_id))
        },
        judgments=evaluation.get_judgments(content_ids, version_id),
        outcomes=evaluation.get_criterion_outcomes(content_ids, version_id),
        ratifications=evaluation.list_ratifications(version_id),
        computed_at=datetime.now(UTC),
    )


def test_the_first_increment_closes_the_loop(
    cleanup, unique, session, namespace, admin, patched_package, register_generator_version
):
    admin_id, email = admin

    # --- the evaluand side: paired registrations, one generator known, one unknown
    generator_id = register_generator_version(f"studies-flow-generator-{unique}")
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

    # --- the fitness projection over the SAME study (ADR-0023)
    projection = _project_fitness(session, study.id)

    # It is not in the report, and it says so about itself.
    assert "fitness" not in report
    assert projection["signal"] == "optimization"
    assert projection["formulaVersion"]

    # The qualities the instrument asserts about, and only those: 16 of the frame's 21.
    # `constructive-alignment`'s four are absent by design (no declared objectives to align
    # against under LearnpackV1), so that dimension does not appear at all.
    study_level = projection["study"]
    assert len(study_level["qualities"]) == 16
    assert "constructive-alignment" not in study_level["dimensions"]

    # The case the whole denominator rule exists for: LearnpackV1 supplies no objectives, so
    # every criterion under that quality is `not_applicable` — undefined, NOT zero. A zero
    # here would have the GA evolve against a gap in the format, not in the generator.
    objectives = study_level["qualities"]["objectives-observable"]
    assert objectives["fitness"] is None
    assert objectives["coverage"]["denominator"] == 0
    assert objectives["coverage"]["notApplicable"] > 0
    assert study_level["dimensions"]["objectives-quality"] == {
        "fitness": None,
        "coverage": {"qualities": 3, "defined": 0},
    }

    # `objectives-quality` is the only dimension left blind. `learning-progression` is not:
    # the audience quality under it still has no supply, but `progression-cognitive-demand`
    # is measured from the lesson bodies, and ONE defined quality is enough for a dimension
    # to have a value. That is the point of the unweighted mean over DEFINED qualities —
    # what cannot be measured is dropped, not scored zero.
    assert study_level["qualities"]["progression-starting-point"]["fitness"] is None
    progression = study_level["dimensions"]["learning-progression"]
    assert progression["coverage"] == {"qualities": 4, "defined": 1}
    assert progression["fitness"] is not None
    assert study_level["qualities"]["progression-cognitive-demand"]["fitness"] is not None

    # What the format DOES supply is measured: the lesson inventory and bodies feed two of the
    # four coherence qualities. The other two wait on an assessor that can read semantics —
    # `not_assessed` keeps them out of the denominator rather than scoring them zero.
    coherence = study_level["dimensions"]["inter-lesson-coherence"]
    assert coherence["coverage"] == {"qualities": 4, "defined": 2}
    assert coherence["fitness"] is not None

    # structural:1's abstentions are counted and named, never charged to the generator.
    assert projection["assessorCoverage"]["notAssessed"] > 0
    assert projection["assessorCoverage"]["ratifiedAssessors"]

    # Generator level accumulates the linked content only, like the report's does.
    assert [g["generatorVersionId"] for g in projection["generators"]] == [str(generator_id)]
    assert projection["generators"][0]["contents"] == 1
    assert projection["unknownExclusions"] == [str(orphan.id)]


def test_an_attributed_content_enters_generator_level_accumulation(
    cleanup, unique, session, namespace, admin, patched_package, register_generator_version
):
    """What the repair act is for (ADR-0024): a content registered with its generator
    unknown is excluded from accumulation, and after attribution it counts."""
    admin_id, email = admin
    generator_id = register_generator_version(f"studies-flow-generator-{unique}")
    orphan = _register_course(cleanup, unique, "late")  # declared unknown at registration

    version_id = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", version_id, email, []) == 0
    track_automated(cleanup, patched_package.name)
    assert run_evaluate(str(orphan.id), version_id, f"{patched_package.name}:1", False) == 0

    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        study = DeclareStudy(studies, uow.events, uow)(
            DeclareStudyCommand(purpose=f"Attribution round ({unique})")
        )
    cleanup["studies"].append(study.id)
    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        PinInstrument(studies, DesignGateway(s), uow.events, uow)(
            PinInstrumentCommand(study_id=study.id, instrument_version_id=version_id)
        )
    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        ComposeDataset(studies, RegistryGateway(s), uow)(
            ComposeDatasetCommand(study_id=study.id, brief_ids=[orphan.brief_id])
        )
    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        OpenStudy(studies, uow.events, uow)(OpenStudyCommand(study_id=study.id))

    # The discovery lands after the dataset was fixed — the report is composed at publish
    # and reads the registry live, so it counts (ADR-0024, an accepted consequence).
    assert run_attribute_generator(orphan.id, generator_id, email) == 0

    with SessionLocal() as s:
        uow, studies = _studies_wiring(s)
        PublishStudy(
            studies=studies,
            reports=SqlAlchemyStudyReportRepository(s),
            registry=RegistryGateway(s),
            evaluation=EvaluationGateway(s),
            design=DesignGateway(s),
            profiling=ProfilingGateway(s),
            publisher=uow.events,
            uow=uow,
        )(PublishStudyCommand(study_id=study.id, published_by=admin_id))

    report = SqlAlchemyStudyReportRepository(session).get(study.id).report
    assert [g["generatorVersionId"] for g in report["generatorLevel"]] == [str(generator_id)]
    assert report["generatorLevel"][0]["contentsCounted"] == 1
    assert report["caveats"]["unknownExclusions"]["contentIds"] == []
