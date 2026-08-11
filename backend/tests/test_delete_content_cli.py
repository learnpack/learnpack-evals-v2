"""`delete-content`: removing a content version nothing has used (ADR-0033).

A development affordance, not a capability of the system — so the interesting tests are the
refusals. Two of the six things it checks have no foreign key behind them (`study_dataset`,
`study_recipe`): a raw DELETE would succeed there and leave a study naming rows that no longer
exist, which is the whole reason this is a command with a check.
"""

import pytest
from sqlalchemy import text

import app.cli as cli
from app.cli import run_delete_content
from app.modules.evaluand_registry.application.register_brief import (
    RegisterBrief,
    RegisterBriefCommand,
)
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id


@pytest.fixture
def register_brief(cleanup):
    def _register(text_: str):
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            brief = RegisterBrief(
                briefs=SqlAlchemyBriefRepository(session), publisher=uow.events, uow=uow
            )(RegisterBriefCommand(brief=text_))
        cleanup["briefs"].append(brief.id)
        return brief.id

    return _register


@pytest.fixture
def register_content(cleanup, unique):
    def _register(slug: str, brief_id=None):
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
                    external_id=f"{slug}-{unique}",
                    consumable_url=f"https://{slug}-{unique}.learn-pack.com/",
                    artifacts=[{"kind": "manifest", "locator": f"{slug}/learn.json"}],
                    brief_id=brief_id,
                    generator_version_id=None,
                )
            )
        cleanup["contents"].append(content.id)
        return content

    return _register


def profile(session, content_id, status: str = "ok") -> None:
    session.execute(
        text(
            "INSERT INTO content_profiles (id, content_id, package_format, adapter_version,"
            " status, profiled_at) VALUES (:id, :c, 'LearnpackV1', :v, :s, now())"
        ),
        {"id": new_id(), "c": content_id, "v": status, "s": status},
    )
    session.commit()


def exists(session, table: str, column: str, value) -> bool:
    return bool(
        session.execute(
            text(f"SELECT 1 FROM {table} WHERE {column} = :v LIMIT 1"),  # noqa: S608 — literals
            {"v": value},
        ).scalar()
    )


# ------------------------------------------------------------------ the happy path


def test_it_removes_the_content_its_profiles_artifacts_events_and_orphaned_brief(
    register_brief, register_content, session, capsys
):
    brief_id = register_brief("Make a course.")
    content = register_content("deletable", brief_id=brief_id)
    profile(session, content.id)
    profile(session, content.id, status="failed")  # a second profile, another adapter version
    assert exists(session, "content_package_artifacts", "content_id", content.id)
    assert exists(session, "events", "aggregate_id", str(content.id))

    assert run_delete_content(content.id) == 0

    assert not exists(session, "contents", "id", content.id)
    assert not exists(session, "content_profiles", "content_id", content.id)
    # Cascades, not statements of our own — the schema does this and the command relies on it.
    assert not exists(session, "content_package_artifacts", "content_id", content.id)
    assert not exists(session, "events", "aggregate_id", str(content.id))
    assert not exists(session, "generation_briefs", "id", content.brief_id)
    assert "2 profile(s)" in capsys.readouterr().out


def test_a_brief_another_content_shares_is_kept(register_brief, register_content, session, capsys):
    """Registration dedupes briefs by hash — the paired design, same briefs and new products
    (ADR-0013). Deleting one product must not take the commission with it."""
    commission = register_brief("One commission, two products.")
    first = register_content("paired-one", brief_id=commission)
    second = register_content("paired-two", brief_id=commission)
    assert first.brief_id == second.brief_id == commission

    assert run_delete_content(first.id) == 0

    assert exists(session, "generation_briefs", "id", second.brief_id)
    assert exists(session, "contents", "id", second.id)
    assert "brief kept" in capsys.readouterr().out


# ------------------------------------------------------------------ the refusals


def test_it_refuses_content_a_study_dataset_names(register_content, session, cleanup, capsys):
    """The case no foreign key protects: `study_dataset` carries the id and nothing else
    (ADR-0006). A raw DELETE would succeed here and leave the study pointing at nothing."""
    content = register_content("in-a-study")
    profile(session, content.id)
    study_id = new_id()
    cleanup["studies"].append(study_id)
    session.execute(
        text("INSERT INTO studies (id, purpose) VALUES (:id, 'a purpose')"),
        {"id": study_id},
    )
    session.execute(
        text("INSERT INTO study_dataset (study_id, content_id) VALUES (:s, :c)"),
        {"s": study_id, "c": content.id},
    )
    session.commit()

    assert run_delete_content(content.id) == 1

    assert "study_dataset" in capsys.readouterr().err
    assert exists(session, "contents", "id", content.id)


def test_a_refusal_leaves_everything_in_place(register_content, session, cleanup):
    """One transaction: a command that refused must not have removed the profile on its way
    to finding out."""
    content = register_content("untouched")
    profile(session, content.id)
    campaign_id = new_id()
    cleanup["campaigns"].append(campaign_id)
    session.execute(
        text(
            "INSERT INTO campaigns (id, instrument_version_id,"
            " required_evaluations_per_content)"
            " VALUES (:id, 'learnpack-course-qa-v1', 1)"
        ),
        {"id": campaign_id},
    )
    session.execute(
        text("INSERT INTO campaign_contents (campaign_id, content_id) VALUES (:k, :c)"),
        {"k": campaign_id, "c": content.id},
    )
    session.commit()

    assert run_delete_content(content.id) == 1

    assert exists(session, "content_profiles", "content_id", content.id)
    assert exists(session, "content_package_artifacts", "content_id", content.id)
    assert exists(session, "generation_briefs", "id", content.brief_id) or content.brief_id is None


def test_an_unknown_content_is_reported_not_ignored(capsys):
    assert run_delete_content(new_id()) == 1
    assert "no content with id" in capsys.readouterr().err


def test_it_refuses_outside_local_mode(register_content, monkeypatch, session, capsys):
    """The single condition that is the whole guard: `Settings` refuses AUTH_MODE=local unless
    the database is local too (ADR-0008), so local mode already implies a local store."""
    content = register_content("production-ish")

    class NotLocal:
        is_local_auth = False

    monkeypatch.setattr(cli, "get_settings", lambda: NotLocal())

    assert run_delete_content(content.id) == 1

    assert "AUTH_MODE=local" in capsys.readouterr().err
    assert exists(session, "contents", "id", content.id)
