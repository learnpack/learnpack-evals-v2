"""An undeclared datum is not asked of a human, end to end (ADR-0053).

The evaluand is a frozen **LearnpackV1** package, which is the case that motivated the
feature: that format has no field for learning objectives or target audience, its adapter
declares no capability for them, and the profile therefore carries **no entry** — not an
`absent` one. The automated side reads that as `not_applicable`, out of the fitness
denominator, so the human side must not record an omission either.

The other branch — an `absent` entry, where the course could have declared the datum and did
not — is exercised over the rule in `test_withheld_items.py` and over storage below, since no
frozen package in the repo produces one.
"""

import pytest
from conftest import fixture_artifact_rows, open_campaign_over
from sqlalchemy import text
from test_content_profiling_commands import profile_content_use_case

from app.modules.content_profiling.application.profile_content import (
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyProfileRepository,
)
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    LearnpackV2Discovery,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.modules.evaluation.domain.evaluation import CriterionScore, Evaluation
from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
from app.modules.identity.domain.assessor import Assessor
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id
from tests.format_cases import FORMAT_CASES

RUBRIC = "learnpack-pedagogical-2.0.0"
COURSE = "introduction-to-generative-ai"

# The four items that rest on a declaration, in the order the instrument lists them.
DECLARATION_ITEMS = {
    "objectives-observable",
    "progression-starting-point",
    "alignment-coverage",
    "alignment-assessment",
}


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def evaluator(as_user, cleanup, unique):
    client = as_user(f"user_ada_{unique}", f"ada-{unique}@example.com", "Ada")
    assessor_id = client.get("/me").json()["assessor_id"]
    cleanup["assessors"].append(assessor_id)
    return client, assessor_id


@pytest.fixture
def profiled_v1_course(cleanup, unique, namespace):
    """Registered with its real artifacts and profiled — so the profile is a real statement
    about what this format declares, not a row a test wrote."""
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
                external_id=f"withheld-{unique}",
                consumable_url=f"https://withheld-{unique}.learn-pack.com/",
                artifacts=fixture_artifact_rows(COURSE),
                generator_version_id=None,
            )
        )
    cleanup["contents"].append(content.id)
    with SessionLocal() as session:
        profile_content_use_case(session)(ProfileContentCommand(content_id=content.id))
    return str(content.id)


@pytest.fixture
def assignment(admin, evaluator, profiled_v1_course, cleanup):
    _, assessor_id = evaluator
    campaign = open_campaign_over(
        admin,
        cleanup,
        [profiled_v1_course],
        name="Withheld items campaign",
        instrument_version_id=RUBRIC,
    )
    created = admin.post(
        f"/admin/campaigns/{campaign['campaign_id']}/assignments",
        json={"content_id": profiled_v1_course, "assessor_id": assessor_id},
    )
    assert created.status_code == 201, created.text
    return created.json()["assignment_id"]


def test_a_format_that_cannot_declare_the_datum_does_not_get_asked(evaluator, assignment):
    client, _ = evaluator

    detail = client.get(f"/assignments/{assignment}").json()

    asked = {c["criterion_id"] for c in detail["criteria"]}
    assert len(asked) == 8
    assert asked.isdisjoint(DECLARATION_ITEMS)
    assert detail["withheld_count"] == 4


def test_the_withheld_items_are_recorded_without_a_score(evaluator, assignment, session):
    """Exact coverage still holds over all twelve — the four the rater never saw are covered
    by derived rows — and none of them carries a number, because nothing was askable."""
    client, _ = evaluator
    detail = client.get(f"/assignments/{assignment}").json()
    client.post(f"/assignments/{assignment}/open")

    submitted = client.post(
        "/evaluations",
        json={
            "assignment_id": assignment,
            "scores": [
                {"criterion_id": c["criterion_id"], "score": 4, "comment": None}
                for c in detail["criteria"]
            ],
        },
    )
    assert submitted.status_code == 201, submitted.text

    rows = dict(
        session.execute(
            text("SELECT criterion_id, derived FROM criterion_scores WHERE evaluation_id = :e"),
            {"e": submitted.json()["evaluation_id"]},
        ).all()
    )
    assert len(rows) == 12
    assert {cid for cid, derived in rows.items() if derived} == DECLARATION_ITEMS

    scores = dict(
        session.execute(
            text("SELECT criterion_id, score FROM criterion_scores WHERE evaluation_id = :e"),
            {"e": submitted.json()["evaluation_id"]},
        ).all()
    )
    assert all(scores[cid] is None for cid in DECLARATION_ITEMS)
    assert all(scores[cid] == 4 for cid in scores if cid not in DECLARATION_ITEMS)


def test_a_client_cannot_answer_a_withheld_item(evaluator, assignment, session):
    """What an item is worth when nobody was asked is a mechanical fact. A rater who sends
    all twelve anyway does not get to decide the four."""
    client, _ = evaluator
    client.post(f"/assignments/{assignment}/open")
    detail = client.get(f"/assignments/{assignment}").json()

    every_item = [{"criterion_id": c["criterion_id"], "score": 5} for c in detail["criteria"]] + [
        {"criterion_id": cid, "score": 5} for cid in sorted(DECLARATION_ITEMS)
    ]
    submitted = client.post(
        "/evaluations", json={"assignment_id": assignment, "scores": every_item}
    )
    assert submitted.status_code == 201, submitted.text

    stored = dict(
        session.execute(
            text("SELECT criterion_id, score FROM criterion_scores WHERE evaluation_id = :e"),
            {"e": submitted.json()["evaluation_id"]},
        ).all()
    )
    assert all(stored[cid] is None for cid in DECLARATION_ITEMS)


def test_the_report_tells_withheld_apart_from_abstained(admin, evaluator, assignment, session):
    """Both come back with no average. Only `withheld` says which is which — a result
    without its coverage misleads (ADR-0011 §3)."""
    client, _ = evaluator
    detail = client.get(f"/assignments/{assignment}").json()
    client.post(f"/assignments/{assignment}/open")
    asked = [c["criterion_id"] for c in detail["criteria"]]

    scores = [{"criterion_id": cid, "score": 4, "comment": None} for cid in asked]
    scores[0] = {"criterion_id": asked[0], "score": None, "comment": None}  # an abstention
    submitted = client.post("/evaluations", json={"assignment_id": assignment, "scores": scores})
    assert submitted.status_code == 201, submitted.text

    content_id = str(
        session.execute(
            text("SELECT content_id FROM evaluations WHERE id = :e"),
            {"e": submitted.json()["evaluation_id"]},
        ).scalar_one()
    )
    report = admin.get("/admin/reports/scores").json()
    summaries = {
        c["criterion_id"]: c
        for entry in report["contents"]
        if entry["content_id"] == content_id
        for c in entry["criteria"]
    }

    withheld = summaries["objectives-observable"]
    assert withheld["average"] is None and withheld["withheld"] is True

    abstained = summaries[asked[0]]
    assert abstained["average"] is None and abstained["withheld"] is False

    answered = summaries[asked[1]]
    assert answered["average"] == 4.0 and answered["withheld"] is False


def test_a_derived_score_can_carry_the_bottom_of_the_scale(requires_db, cleanup, unique):
    """The other branch's storage: where the course COULD have declared the datum and did
    not, the derived row carries the scale minimum, the way ADR-0021 records a derived fail
    rather than leaving it to be recomputed."""
    evaluation_id = new_id()
    assessor_id, content_id = new_id(), new_id()
    with SessionLocal() as session:
        SqlAlchemyAssessorRepository(session).add(
            Assessor(
                id=assessor_id,
                auth_provider="local",
                auth_subject=f"derived-{unique}@example.com",
                email=f"derived-{unique}@example.com",
            )
        )
        session.execute(
            text(
                "INSERT INTO contents (id, package_format, external_id, version)"
                " VALUES (:i, 'LearnpackV1', :x, '1')"
            ),
            {"i": content_id, "x": f"derived-{unique}"},
        )
        session.commit()
        cleanup["assessors"].append(assessor_id)
        cleanup["contents"].append(content_id)

        evaluation = Evaluation.submit(
            evaluation_id=evaluation_id,
            assessor_id=assessor_id,
            content_id=content_id,
            instrument_version_id=RUBRIC,
            scores=[
                CriterionScore(criterion_id="objectives-observable", score=1, derived=True),
                CriterionScore(criterion_id="coherence-reinforcement", score=4),
            ],
            rubric_criterion_ids=["objectives-observable", "coherence-reinforcement"],
        )
        SqlAlchemyEvaluationRepository(session).add(evaluation)
        session.commit()

        stored = dict(
            session.execute(
                text(
                    "SELECT criterion_id, score || ':' || derived FROM criterion_scores"
                    " WHERE evaluation_id = :e"
                ),
                {"e": evaluation_id},
            ).all()
        )
    assert stored == {
        "objectives-observable": "1:true",
        "coherence-reinforcement": "4:false",
    }


# --------------------------------------------------------------------- ADR-0057


@pytest.fixture
def profiled_v2_course(cleanup, unique, namespace):
    """A format that DOES declare objectives and audience — the other branch of ADR-0053,
    and the only one where there is anything to show the rater."""
    case = FORMAT_CASES["LearnpackV2"]
    discovered = LearnpackV2Discovery().discover(
        FilesystemPackageRoot(case.fixture_dir, locator_base=case.fixture_dir.name)
    )
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
                package_format="LearnpackV2",
                external_id=f"declared-{unique}",
                consumable_url=f"https://declared-{unique}.learn-pack.com/",
                artifacts=[
                    {"kind": a.kind, "locator": a.locator, "format": a.format}
                    for a in discovered.artifacts
                ],
                generator_version_id=None,
            )
        )
    cleanup["contents"].append(content.id)
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        ProfileContent(
            profiles=SqlAlchemyProfileRepository(session),
            contents=RegistryContentGateway(session),
            namespace=DesignNamespaceGateway(session),
            adapters=ADAPTERS_BY_FORMAT,
            fetcher=FilesystemPackageFetcher(case.fixture_dir.parent),
            publisher=uow.events,
            uow=uow,
        )(ProfileContentCommand(content_id=content.id))
    return str(content.id)


@pytest.fixture
def declared_assignment(admin, evaluator, profiled_v2_course, cleanup):
    _, assessor_id = evaluator
    campaign = open_campaign_over(
        admin,
        cleanup,
        [profiled_v2_course],
        name="Declared data campaign",
        instrument_version_id=RUBRIC,
    )
    created = admin.post(
        f"/admin/campaigns/{campaign['campaign_id']}/assignments",
        json={"content_id": profiled_v2_course, "assessor_id": assessor_id},
    )
    assert created.status_code == 201, created.text
    return created.json()["assignment_id"]


def test_the_rater_is_shown_the_data_their_items_rest_on(evaluator, declared_assignment):
    client, _ = evaluator

    detail = client.get(f"/assignments/{declared_assignment}").json()

    assert {c["criterion_id"] for c in detail["criteria"]} >= DECLARATION_ITEMS
    assert detail["withheld_count"] == 0

    # Ordered by the first asked item that rests on each, so the block reads in the order
    # the form does: objectives (item 1) before audience (item 2).
    assert [d["requirement_id"] for d in detail["declared"]] == [
        "learning_objectives",
        "target_audience",
    ]
    objectives, audience = detail["declared"]
    assert isinstance(objectives["value"], list) and objectives["value"]
    assert all(isinstance(statement, str) for statement in objectives["value"])
    assert isinstance(audience["value"], str) and audience["value"]

    # The screen marks the items that rest on a datum from what the item itself declares.
    by_id = {c["criterion_id"]: c for c in detail["criteria"]}
    assert by_id["objectives-observable"]["required_data"] == ["learning_objectives"]
    assert by_id["progression-starting-point"]["required_data"] == ["target_audience"]
    assert by_id["coherence-logical-sequence"]["required_data"] == []


def test_nothing_is_shown_for_a_question_nobody_was_asked(evaluator, assignment):
    """The V1 course: those four items are withheld, so there is no datum to show and no
    orphan value on screen (ADR-0057 §2)."""
    client, _ = evaluator

    detail = client.get(f"/assignments/{assignment}").json()

    assert detail["declared"] == []
    assert all(c["required_data"] == [] for c in detail["criteria"])


def test_a_value_the_screen_cannot_read_is_not_sent(
    evaluator, declared_assignment, profiled_v2_course, session
):
    """The contract is `str | list[str]` (ADR-0057 §4). A shape nobody designed for a reader
    is left out — and its item is still asked, because the course did declare it."""
    session.execute(
        text(
            """
            UPDATE profile_entries SET value = '{"objectives": []}'::jsonb
             WHERE data_requirement_id = 'learning_objectives'
               AND profile_id IN (SELECT id FROM content_profiles WHERE content_id = :c)
            """
        ),
        {"c": profiled_v2_course},
    )
    session.commit()

    client, _ = evaluator
    detail = client.get(f"/assignments/{declared_assignment}").json()

    assert [d["requirement_id"] for d in detail["declared"]] == ["target_audience"]
    assert "objectives-observable" in {c["criterion_id"] for c in detail["criteria"]}
