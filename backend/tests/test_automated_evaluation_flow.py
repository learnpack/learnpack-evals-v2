"""The automated path end to end: publish → profile → ratify → evaluate → judgment.

Uses a COPY of the real instrument under a throwaway lineage (`qa-copy-<unique>`) plus a
registry-patched clone of the `structural` package bound to that lineage — the real
instrument id stays untouched (other tests rely on it remaining a draft). The evaluand is
the frozen `introduction-to-generative-ai` package, whose lesson ids include the real
numbering drift ('05', '06') — a deterministic structural finding.

Also here (same fixtures): the judgment-policy replay test and the dry-run test.
"""

import copy
import dataclasses
from uuid import UUID

import pytest
import yaml
from sqlalchemy import text
from test_content_profiling_commands import profile_content_use_case
from test_instrument_authoring_api import import_spec

import app.main  # noqa: F401 — wires the judgment policy into the global dispatcher
from app.cli import _demo_artifacts, run_evaluate, run_ratify_assessor
from app.modules.content_profiling.application.profile_content import ProfileContentCommand
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation.infrastructure.policies import on_evaluation_completed
from app.modules.evaluation.public import EvaluationQueries
from app.modules.evaluation_design.application.publish_instrument import (
    PublishInstrument,
    PublishInstrumentCommand,
)
from app.modules.evaluation_design.infrastructure.repository import (
    SqlAlchemyDataRequirementRepository,
    SqlAlchemyInstrumentRepository,
    SqlAlchemyReferenceDataRepository,
)
from app.modules.evaluation_design.public import InstrumentQueries
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.events import DomainEvent
from tests.conftest import INSTRUMENT_SPEC_FILE

REAL_SPEC = yaml.safe_load(INSTRUMENT_SPEC_FILE.read_text(encoding="utf-8"))
COURSE = "introduction-to-generative-ai"


def copy_spec(unique: str, version: str = "v1") -> dict:
    spec = copy.deepcopy(REAL_SPEC)
    spec["instrument_id"] = f"qa-copy-{unique}"
    spec["version"] = version
    return spec


def publish_instrument(cleanup, payload: dict, published_by: str) -> str:
    # revise_definitions: the `namespace` fixture mints these ids with test definitions;
    # the real YAML rewords them — the deliberate act exists for exactly this.
    instrument_id = import_spec(cleanup, payload, revise_definitions=True)
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        PublishInstrument(
            instruments=SqlAlchemyInstrumentRepository(session),
            data_requirements=SqlAlchemyDataRequirementRepository(session),
            reference=SqlAlchemyReferenceDataRepository(session),
            publisher=uow.events,
            uow=uow,
        )(
            PublishInstrumentCommand(
                instrument_version_id=instrument_id, published_by=UUID(published_by)
            )
        )
    return instrument_id


def track_automated(cleanup, name: str, version: str = "1") -> str:
    """Register the CLI-created automated assessor row for cleanup; returns its id."""
    with SessionLocal() as session:
        row = SqlAlchemyAssessorRepository(session).get_automated(name, version)
    assert row is not None
    cleanup["assessors"].append(str(row.id))
    return str(row.id)


@pytest.fixture
def admin(register_assessor, unique):
    email = f"admin-{unique}@example.com"
    assessor_id = register_assessor(f"user_admin_{unique}", email, "Admin")
    return assessor_id, email


@pytest.fixture
def patched_package(unique, monkeypatch):
    """The structural package, cloned onto the throwaway lineage (same coverage)."""
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


@pytest.fixture
def profiled_course(cleanup, unique, namespace):
    """The frozen intro course, registered with its real artifacts and profiled."""
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        content = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(
            RegisterContentVersionCommand(
                package_format="LearnpackV1",
                external_id=f"e2e-course-{unique}",
                consumable_url=f"https://e2e-{unique}.learn-pack.com/",
                artifacts=_demo_artifacts(COURSE),
                # This flow is about the automated path, not attribution (ADR-0024).
                generator_version_id=None,
            )
        )
    cleanup["contents"].append(content.id)
    with SessionLocal() as session:
        profile_content_use_case(session)(ProfileContentCommand(content_id=content.id))
    return content.id


def outcome_rows(session, content_id):
    return (
        session.execute(
            text(
                "SELECT o.criterion_id, o.outcome, o.derived, o.quote, o.failure_mode "
                "FROM criterion_outcomes o JOIN evaluations e ON e.id = o.evaluation_id "
                "WHERE e.content_id = :c ORDER BY e.occurred_at, o.criterion_id"
            ),
            {"c": content_id},
        )
        .mappings()
        .all()
    )


def event_types(session, aggregate_id: str) -> list[str]:
    return [
        row[0]
        for row in session.execute(
            text("SELECT event_type FROM events WHERE aggregate_id = :id ORDER BY id"),
            {"id": aggregate_id},
        )
    ]


def test_full_automated_path(cleanup, unique, session, admin, patched_package, profiled_course):
    admin_id, email = admin
    instrument_id = publish_instrument(cleanup, copy_spec(unique), admin_id)

    assert run_ratify_assessor(patched_package.name, "1", instrument_id, email, []) == 0
    assessor_id = track_automated(cleanup, patched_package.name)

    assert (
        run_evaluate(str(profiled_course), instrument_id, f"{patched_package.name}:1", False) == 0
    )

    # --- outcomes: exact five-state coverage over the 11 criteria ---
    rows = outcome_rows(session, profiled_course)
    assert len(rows) == 11
    by_outcome: dict[str, list] = {}
    for row in rows:
        by_outcome.setdefault(row["outcome"], []).append(row)
    # Demand without supply on LearnpackV1: the four criteria over undeclared data.
    assert {r["criterion_id"] for r in by_outcome["not_applicable"]} == {
        "cr-objectives-min-count",
        "cr-objectives-observable-verbs",
        "cr-audience-declared",
        "cr-prerequisites-declared",
    }
    # The three judgment criteria the assessor abstains from (data present).
    assert {r["criterion_id"] for r in by_outcome["not_assessed"]} == {
        "cr-module-single-topic",
        "cr-arc-character",
        "cr-modules-intro-then-apply",
    }
    scored = by_outcome.get("pass", []) + by_outcome.get("fail", [])
    assert len(scored) == 4
    assert all(not r["derived"] and r["quote"] for r in scored)
    # The frozen package's real numbering drift ('05', '06') fails structurally.
    drift = next(r for r in rows if r["criterion_id"] == "cr-module-structure-well-formed")
    assert drift["outcome"] == "fail"
    assert "drift" in drift["failure_mode"].lower()

    evaluation = (
        session.execute(
            text(
                "SELECT id, profile_id, attempt FROM evaluations WHERE content_id = :c "
                "ORDER BY occurred_at DESC LIMIT 1"
            ),
            {"c": profiled_course},
        )
        .mappings()
        .one()
    )
    assert evaluation["profile_id"] is not None
    assert evaluation["attempt"] == 1
    metric_count = session.execute(
        text("SELECT count(*) FROM computed_metrics WHERE evaluation_id = :id"),
        {"id": evaluation["id"]},
    ).scalar_one()
    assert metric_count > 0

    # --- the judgment the policy derived, synchronously post-commit ---
    judgment = (
        session.execute(
            text("SELECT id, evaluation_id, coverage FROM quality_judgments WHERE content_id = :c"),
            {"c": profiled_course},
        )
        .mappings()
        .one()
    )
    assert judgment["evaluation_id"] == evaluation["id"]
    # Claims whose criteria are ALL not_applicable stay out of the denominator.
    assert set(judgment["coverage"]["excludedClaims"]) == {
        "cl-objectives-declared",
        "cl-audience-declared",
    }
    claims = dict(
        session.execute(
            text("SELECT claim_id, status FROM judgment_claims WHERE judgment_id = :id"),
            {"id": judgment["id"]},
        ).all()
    )
    assert len(claims) == 3
    assert claims["cl-course-modular"] == "refuted"  # the cited counterexample
    findings = (
        session.execute(
            text("SELECT criterion_id, quote, failure_mode FROM findings WHERE judgment_id = :id"),
            {"id": judgment["id"]},
        )
        .mappings()
        .all()
    )
    assert any(
        f["criterion_id"] == "cr-module-structure-well-formed" and f["quote"] for f in findings
    )

    # --- the un-aggregated outcomes behind that judgment (what ADR-0023 reads) ---
    outcomes = EvaluationQueries(session).get_criterion_outcomes([profiled_course], instrument_id)
    instrument = InstrumentQueries(session).get_instrument(instrument_id)
    assert instrument is not None
    assert {o.criterion_id for o in outcomes} == set(instrument.criterion_ids)  # exact coverage
    assert all(o.judgment_id == judgment["id"] for o in outcomes)
    assert any(o.outcome == "not_applicable" for o in outcomes)  # the ADR-0017 unmet demand
    # The un-aggregated form must agree with the aggregated one, claim by claim: the same
    # states, counted there and identified here. Note the excluded claims have no
    # `judgment_claims` row at all — which is why ADR-0023 attributes criteria from the
    # instrument and never from the judgment.
    state_key = {
        "pass": "pass",
        "fail": "fail",
        "no_evidence": "noEvidence",
        "not_applicable": "notApplicable",
        "not_assessed": "notAssessed",
    }
    outcome_of = {o.criterion_id: o.outcome for o in outcomes}
    for claim_id, basis in session.execute(
        text("SELECT claim_id, evidence_basis FROM judgment_claims WHERE judgment_id = :id"),
        {"id": judgment["id"]},
    ):
        recomputed: dict[str, int] = {}
        for criterion in instrument.criteria:
            if claim_id in criterion.claim_ids:
                state = state_key[outcome_of[criterion.criterion_id]]
                recomputed[state] = recomputed.get(state, 0) + 1
        assert {k: v for k, v in basis.items() if v} == recomputed

    # --- events ---
    assert "EvaluationCompleted" in event_types(session, str(evaluation["id"]))
    judgment_events = event_types(session, str(judgment["id"]))
    assert judgment_events[0] == "QualityJudgmentPublished"
    assert judgment_events.count("FindingRaised") == len(findings)

    # --- repetition: same triple, attempt increments, judgments stay append-only ---
    assert (
        run_evaluate(str(profiled_course), instrument_id, f"{patched_package.name}:1", False) == 0
    )
    attempts = [
        row[0]
        for row in session.execute(
            text(
                "SELECT attempt FROM evaluations WHERE content_id = :c AND assessor_id = :a "
                "ORDER BY attempt"
            ),
            {"c": profiled_course, "a": UUID(assessor_id)},
        )
    ]
    assert attempts == [1, 2]
    judgment_count = session.execute(
        text("SELECT count(*) FROM quality_judgments WHERE content_id = :c"),
        {"c": profiled_course},
    ).scalar_one()
    assert judgment_count == 2  # append-only; the most recent is the current one


def test_evaluate_guards(cleanup, unique, session, admin, patched_package, profiled_course):
    admin_id, email = admin
    # A draft is not evaluable on the real path...
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)
    assert run_evaluate(str(profiled_course), draft_id, f"{patched_package.name}:1", False) == 1
    # ...and a published version without ratification is not either.
    published = publish_instrument(cleanup, copy_spec(unique, version="v9"), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", published, email, []) == 0
    track_automated(cleanup, patched_package.name)
    other = publish_instrument(cleanup, copy_spec(unique, version="v10"), admin_id)
    assert run_evaluate(str(profiled_course), other, f"{patched_package.name}:1", False) == 1


def test_judgment_policy_replay_is_idempotent(
    cleanup, unique, session, admin, patched_package, profiled_course
):
    admin_id, email = admin
    instrument_id = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", instrument_id, email, []) == 0
    track_automated(cleanup, patched_package.name)
    assert (
        run_evaluate(str(profiled_course), instrument_id, f"{patched_package.name}:1", False) == 0
    )

    # Replay the stored event, exactly as reprocessing from the events table would.
    stored = (
        session.execute(
            text(
                "SELECT aggregate_type, aggregate_id, event_type, payload FROM events "
                "WHERE event_type = 'EvaluationCompleted' AND payload->>'contentId' = :c"
            ),
            {"c": str(profiled_course)},
        )
        .mappings()
        .one()
    )
    replayed = DomainEvent(
        event_type=stored["event_type"],
        aggregate_type=stored["aggregate_type"],
        aggregate_id=stored["aggregate_id"],
        payload=stored["payload"],
    )
    on_evaluation_completed(replayed)
    on_evaluation_completed(replayed)

    count = session.execute(
        text("SELECT count(*) FROM quality_judgments WHERE content_id = :c"),
        {"c": profiled_course},
    ).scalar_one()
    assert count == 1  # one evaluation, one judgment — replays derive nothing new
    published_events = session.execute(
        text(
            "SELECT count(*) FROM events WHERE event_type = 'QualityJudgmentPublished' "
            "AND payload->>'contentId' = :c"
        ),
        {"c": str(profiled_course)},
    ).scalar_one()
    assert published_events == 1


def test_dry_run_persists_nothing_and_accepts_drafts(
    cleanup, unique, session, patched_package, profiled_course, capsys
):
    # A DRAFT — never published (revise: `namespace` minted test definitions first).
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)

    def counts() -> tuple[int, int, int]:
        return (
            session.execute(text("SELECT count(*) FROM evaluations")).scalar_one(),
            session.execute(text("SELECT count(*) FROM quality_judgments")).scalar_one(),
            session.execute(text("SELECT count(*) FROM events")).scalar_one(),
        )

    before = counts()
    assert run_evaluate(str(profiled_course), draft_id, f"{patched_package.name}:1", True) == 0
    assert counts() == before  # zero writes: no evaluation, no judgment, no events

    out = capsys.readouterr().out
    assert "cr-module-structure-well-formed" in out
    assert "dry run: nothing persisted" in out
    assert "refuted" in out  # the claims summary rides along
