"""Declaring a deployment after registration (ADR-0054).

Shaped like `test_generator_attribution.py`, because the act is shaped like attribution — and
different in the one place that matters: this one may be repeated. The rule is stated twice,
in the aggregate and in the UPDATE's WHERE, so it is tested twice: through the use case, and
against the repository alone, which is what holds if two admins declare at the same moment.
"""

from pathlib import Path
from uuid import uuid4

import pytest
from conftest import fixture_artifact_rows
from sqlalchemy import text
from test_content_profiling_commands import profile_content_use_case

from app.cli import _deployments_from_csv, _UnusableDeploymentList, run_declare_deployment
from app.modules.content_profiling.application.profile_content import ProfileContentCommand
from app.modules.evaluand_registry.application.declare_consumable_url import (
    ConsumableUrlChangedMeanwhile,
    DeclareConsumableUrl,
    DeclareConsumableUrlCommand,
)
from app.modules.evaluand_registry.application.errors import ContentNotFound
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.domain.content import InvalidContent
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.modules.identity.domain.assessor import Assessor
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id

FIRST = "https://a-course.learn-pack.com/"
MOVED = "https://a-course.pages.dev/"


@pytest.fixture
def content(cleanup, unique):
    """A version registered the way `courses/` registers one: with no deployment declared."""

    def _register(consumable_url=None, external_id=None, version="1"):
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            registered = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
            )(
                RegisterContentVersionCommand(
                    package_format="LearnpackV1",
                    external_id=external_id or f"deploy-course-{unique}",
                    consumable_url=consumable_url,
                    version=version,
                    generator_version_id=None,
                )
            )
        cleanup["contents"].append(registered.id)
        return registered

    return _register


@pytest.fixture
def admin_email(cleanup, unique):
    email = f"deployer-{unique}@example.com"
    with SessionLocal() as session:
        assessor = Assessor(id=new_id(), auth_provider="local", auth_subject=email, email=email)
        SqlAlchemyAssessorRepository(session).add(assessor)
        session.commit()
    cleanup["assessors"].append(assessor.id)
    return email


def declare(content_id, url, declared_by=None):
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        return DeclareConsumableUrl(
            contents=SqlAlchemyContentRepository(session), publisher=uow.events, uow=uow
        )(
            DeclareConsumableUrlCommand(
                content_id=content_id, consumable_url=url, declared_by=declared_by or uuid4()
            )
        )


def row(session, content_id):
    return (
        session.execute(
            text(
                "SELECT consumable_url, consumable_url_declared_by, consumable_url_declared_at"
                " FROM contents WHERE id = :id"
            ),
            {"id": content_id},
        )
        .mappings()
        .one()
    )


def events_for(session, content_id):
    return (
        session.execute(
            text(
                "SELECT event_type, payload FROM events WHERE aggregate_id = :id"
                " ORDER BY occurred_at"
            ),
            {"id": str(content_id)},
        )
        .mappings()
        .all()
    )


# --------------------------------------------------------------------------- the act


def test_a_registered_version_can_be_pointed_at_its_deployment(content, requires_db):
    """The case the campaign needs: registered from `courses/` with no URL, deployed after."""
    registered = content()
    declarer = new_id()

    declare(registered.id, FIRST, declared_by=declarer)

    with SessionLocal() as session:
        stored = row(session, registered.id)
    assert stored["consumable_url"] == FIRST
    assert stored["consumable_url_declared_by"] == declarer
    assert stored["consumable_url_declared_at"] is not None


def test_a_deployment_that_moved_is_redeclared_and_the_change_is_recorded(content, requires_db):
    """Where this parts from ADR-0024: a deployment is a statement about the world right
    now, so it may be repeated — and `from`/`to` is what makes the move readable."""
    registered = content(consumable_url=FIRST)

    declare(registered.id, MOVED)

    with SessionLocal() as session:
        assert row(session, registered.id)["consumable_url"] == MOVED
        declared = [
            e
            for e in events_for(session, registered.id)
            if e["event_type"] == "ConsumableUrlDeclared"
        ]
    assert len(declared) == 1
    assert declared[0]["payload"]["from"] == FIRST
    assert declared[0]["payload"]["to"] == MOVED


def test_declaring_the_same_url_changes_nothing_and_emits_nothing(content, requires_db):
    """A change that changed nothing must not enter the outbox (ADR-0054 §3)."""
    registered = content(consumable_url=FIRST)

    declare(registered.id, FIRST)

    with SessionLocal() as session:
        stored = row(session, registered.id)
        declared = [
            e
            for e in events_for(session, registered.id)
            if e["event_type"] == "ConsumableUrlDeclared"
        ]
    assert stored["consumable_url"] == FIRST
    # Untouched: a no-op does not even record an actor, because nobody decided anything.
    assert stored["consumable_url_declared_by"] is None
    assert declared == []


def test_clearing_a_declaration_is_refused(content, requires_db):
    """Named rather than silent (ADR-0054 §5): `None` already means *none declared*."""
    registered = content(consumable_url=FIRST)

    with pytest.raises(InvalidContent, match="http"):
        declare(registered.id, None)


def test_a_url_that_is_not_http_is_refused(content, requires_db):
    registered = content()

    with pytest.raises(InvalidContent, match="http"):
        declare(registered.id, "ftp://a-course.example.com/")


def test_an_unregistered_content_is_refused(requires_db):
    with pytest.raises(ContentNotFound):
        declare(new_id(), FIRST)


def test_the_write_is_conditional_on_what_was_read(content, requires_db):
    """Two admins declaring at once: the second is told, not silently overwritten. The
    aggregate states the rule where it is read; this is what holds it in the database."""
    registered = content(consumable_url=FIRST)
    declare(registered.id, MOVED)  # somebody else got there first

    with SessionLocal() as session:
        uow = UnitOfWork(session)
        contents = SqlAlchemyContentRepository(session)
        stale = contents.get_by_id(registered.id)
        stale.consumable_url = "https://third.example.com/"
        # `previous` is what this caller believed, which is no longer what the row holds.
        assert contents.declare_consumable_url(stale, previous=FIRST) is False
        uow  # noqa: B018 — the session is rolled back by the fixture


def test_the_use_case_reports_a_lost_race(content, requires_db, monkeypatch):
    registered = content()

    monkeypatch.setattr(
        SqlAlchemyContentRepository, "declare_consumable_url", lambda *_args, **_kw: False
    )
    with pytest.raises(ConsumableUrlChangedMeanwhile):
        declare(registered.id, FIRST)


# --------------------------------------------------------------------------- the CSV


def test_the_csv_is_read_as_forgivingly_as_the_other_one(tmp_path: Path):
    path = tmp_path / "deployments.csv"
    path.write_text(
        "course,deployed at\n"
        "\n"
        "html-fundamentals,https://html.learn-pack.com/\n"
        "# parked-course,https://parked.example.com/\n"
        "html-fundamentals,https://html.learn-pack.com/\n"
        "git-basics,https://git.learn-pack.com/\n",
        encoding="utf-8",
    )

    assert _deployments_from_csv(path) == [
        ("html-fundamentals", "https://html.learn-pack.com/"),
        ("git-basics", "https://git.learn-pack.com/"),
    ]


def test_one_course_with_two_deployments_is_refused(tmp_path: Path):
    """Not a duplicate but a disagreement, and not this command's to settle."""
    path = tmp_path / "conflicting.csv"
    path.write_text(
        "html-fundamentals,https://one.example.com/\n"
        "html-fundamentals,https://other.example.com/\n",
        encoding="utf-8",
    )

    with pytest.raises(_UnusableDeploymentList, match="twice with different URLs"):
        _deployments_from_csv(path)


def test_a_row_without_a_url_is_refused(tmp_path: Path):
    path = tmp_path / "no-url.csv"
    path.write_text(
        "course,deployed at\nhtml-fundamentals,https://html.learn-pack.com/\ngit-basics,\n",
        encoding="utf-8",
    )

    with pytest.raises(_UnusableDeploymentList, match="no http"):
        _deployments_from_csv(path)


# --------------------------------------------------------------------------- the command


def test_the_command_declares_a_batch_and_says_what_it_did(
    content, admin_email, capsys, requires_db, unique
):
    first = content(external_id=f"batch-one-{unique}")
    second = content(external_id=f"batch-two-{unique}", consumable_url=FIRST)

    code = run_declare_deployment(
        "LearnpackV1",
        admin_email,
        [(first.external_id, FIRST), (second.external_id, FIRST)],
    )

    assert code == 0
    printed = capsys.readouterr().out
    assert f"declared    {first.external_id}" in printed
    assert f"unchanged   {second.external_id}" in printed
    assert "2/2 declared" in printed


def test_an_unknown_slug_fails_the_run(content, admin_email, capsys, requires_db, unique):
    """A 40-row run must not half-succeed quietly."""
    known = content(external_id=f"known-{unique}")

    code = run_declare_deployment(
        "LearnpackV1", admin_email, [(known.external_id, FIRST), ("nobody-here", FIRST)]
    )

    assert code == 1
    assert "not found   nobody-here" in capsys.readouterr().err


def test_a_slug_with_two_versions_is_refused_by_name(
    content, admin_email, capsys, requires_db, unique
):
    """`(package_format, external_id)` is the LOGICAL content (ADR-0005); which version is
    deployed is not something a slug settles, so it is not guessed."""
    external_id = f"two-versions-{unique}"
    content(external_id=external_id, version="1")
    content(external_id=external_id, version="2")

    code = run_declare_deployment("LearnpackV1", admin_email, [(external_id, FIRST)])

    assert code == 1
    assert "ambiguous" in capsys.readouterr().err


# --------------------------------------------------------------------------- the endpoint


@pytest.fixture
def admin_client(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def test_the_endpoint_declares_and_reports_the_content(admin_client, content, requires_db):
    registered = content()

    response = admin_client.post(
        f"/admin/contents/{registered.id}/consumable-url", json={"consumable_url": FIRST}
    )

    assert response.status_code == 200, response.text
    assert response.json()["consumable_url"] == FIRST


def test_the_endpoint_refuses_an_unknown_content(admin_client, requires_db):
    response = admin_client.post(
        f"/admin/contents/{new_id()}/consumable-url", json={"consumable_url": FIRST}
    )
    assert response.status_code == 404


def test_the_endpoint_refuses_a_url_that_is_not_http(admin_client, content, requires_db):
    registered = content()
    response = admin_client.post(
        f"/admin/contents/{registered.id}/consumable-url",
        json={"consumable_url": "ftp://a-course.example.com/"},
    )
    assert response.status_code == 422


# ------------------------------------------------------------- what the act does NOT do


def test_declaring_a_deployment_touches_neither_the_profile_nor_the_evaluand(
    cleanup, unique, namespace, requires_db
):
    """The whole point of the act, and the question it will be asked: a profile is built from
    artifact locators and `content_profiling` never reads this field (ADR-0028 §4), so
    declaring a deployment re-extracts nothing and the evaluand keeps its identity.
    """
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        registered = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(
            RegisterContentVersionCommand(
                package_format="LearnpackV1",
                external_id=f"untouched-{unique}",
                consumable_url=None,
                artifacts=fixture_artifact_rows("introduction-to-generative-ai"),
                generator_version_id=None,
            )
        )
    cleanup["contents"].append(registered.id)
    with SessionLocal() as session:
        profile_content_use_case(session)(ProfileContentCommand(content_id=registered.id))

    def snapshot():
        with SessionLocal() as session:
            profile = (
                session.execute(
                    text(
                        "SELECT id, adapter_version, profiled_at, status FROM content_profiles"
                        " WHERE content_id = :c"
                    ),
                    {"c": registered.id},
                )
                .mappings()
                .one()
            )
            entries = session.execute(
                text("SELECT count(*) FROM profile_entries WHERE profile_id = :p"),
                {"p": profile["id"]},
            ).scalar_one()
            content_hash = session.execute(
                text("SELECT content_hash FROM contents WHERE id = :c"), {"c": registered.id}
            ).scalar_one()
        return dict(profile), entries, content_hash

    before = snapshot()
    declare(registered.id, FIRST)
    after = snapshot()

    assert before == after
    with SessionLocal() as session:
        assert row(session, registered.id)["consumable_url"] == FIRST
