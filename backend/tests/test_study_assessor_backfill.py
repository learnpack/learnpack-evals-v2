"""Migration 0019's backfill (ADR-0042 §11).

The schema half runs once per session through `conftest`; what nothing else covers is
*which* studies get a pin and *which author* they get. It is a one-shot statement over data
that already exists, so being wrong is not something a later run corrects: too eager pins a
mixed study to one of its two judges and silently discards the other half of its evidence,
and picking from the wrong population pins a published study to whoever re-evaluated a
course after it was signed — which would then filter that study's own frozen judgments out
of every read of it.

The statement is imported from the migration rather than restated, for the reason the 0015
test gives: two copies and the test pins a fiction.
"""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

MIGRATION = (
    Path(__file__).parent.parent / "alembic" / "versions" / "0019_study_pins_its_assessor.py"
)


def _backfill_sql() -> str:
    spec = importlib.util.spec_from_file_location("migration_0019", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BACKFILL


@pytest.fixture
def world(session, unique):
    """Four studies, one per shape the backfill has to tell apart. Raw rows on purpose:
    the acts that would produce them are exactly the ones this migration exists because
    nobody could perform."""
    version_id = f"pin-backfill-qa-{unique}"
    session.execute(
        text(
            """
            INSERT INTO instrument_versions (id, instrument_id, version, name, purpose, status)
            VALUES (:id, :instrument_id, 'v1', 'Backfill', 'backfill', 'published')
            """
        ),
        {"id": version_id, "instrument_id": f"pin-backfill-{unique}"},
    )

    ids: dict[str, object] = {}

    def assessor(label: str):
        assessor_id = uuid4()
        session.execute(
            text(
                """
                INSERT INTO assessors (id, role, kind, display_name, source_config)
                VALUES (:id, 'evaluator', 'automated', :name,
                        cast(:config as jsonb))
                """
            ),
            {
                "id": assessor_id,
                "name": f"{label}-{unique}",
                "config": json.dumps(
                    {"name": f"{label}-{unique}", "version": "1", "instrumentId": "qa"}
                ),
            },
        )
        return assessor_id

    def content(label: str):
        content_id = uuid4()
        session.execute(
            text(
                """
                INSERT INTO contents
                    (id, package_format, external_id, version, consumable_url,
                     generator_version_id, edit_provenance)
                VALUES (:id, 'LearnpackV1', :external_id, '1', NULL, NULL, 'unknown')
                """
            ),
            {"id": content_id, "external_id": f"pin-backfill-{label}-{unique}"},
        )
        return content_id

    def judgment(assessor_id, content_id, *, days_ago: int):
        evaluation_id, judgment_id = uuid4(), uuid4()
        session.execute(
            text(
                """
                INSERT INTO evaluations
                    (id, assessor_id, content_id, instrument_version_id, attempt)
                VALUES (:id, :assessor_id, :content_id, :version_id, 1)
                """
            ),
            {
                "id": evaluation_id,
                "assessor_id": assessor_id,
                "content_id": content_id,
                "version_id": version_id,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO quality_judgments
                    (id, evaluation_id, content_id, instrument_version_id, derived_at, coverage)
                VALUES (:id, :evaluation_id, :content_id, :version_id,
                        now() - make_interval(days => :days_ago), '{}'::jsonb)
                """
            ),
            {
                "id": judgment_id,
                "evaluation_id": evaluation_id,
                "content_id": content_id,
                "version_id": version_id,
                "days_ago": days_ago,
            },
        )
        return judgment_id

    def study(label: str, content_ids, *, published_judgments=None):
        study_id = uuid4()
        session.execute(
            text(
                """
                INSERT INTO studies (id, purpose, status, instrument_version_id, published_at)
                VALUES (:id, :purpose, :status, :version_id, :published_at)
                """
            ),
            {
                "id": study_id,
                "purpose": f"backfill {label} {unique}",
                "status": "published" if published_judgments else "open",
                "version_id": version_id,
                "published_at": "2026-08-01T00:00:00+00:00" if published_judgments else None,
            },
        )
        for content_id in content_ids:
            session.execute(
                text("INSERT INTO study_dataset (study_id, content_id) VALUES (:s, :c)"),
                {"s": study_id, "c": content_id},
            )
        if published_judgments:
            session.execute(
                text(
                    """
                    INSERT INTO study_reports (study_id, report, published_at)
                    VALUES (:id, cast(:report as jsonb), now())
                    """
                ),
                {
                    "id": study_id,
                    "report": json.dumps(
                        {
                            "judgmentIdsUsed": {
                                str(c): str(j) for c, j in published_judgments.items()
                            }
                        }
                    ),
                },
            )
        return study_id

    alice, bob = assessor("alice"), assessor("bob")
    one, two, three, four = (content(n) for n in ("one", "two", "three", "four"))

    judgment(alice, one, days_ago=1)
    judgment(bob, two, days_ago=1)
    signed = judgment(alice, four, days_ago=5)
    # Re-evaluated after publication, by someone else: the newest judgment on that course,
    # and the one the frozen report never saw.
    judgment(bob, four, days_ago=1)

    ids["alice"], ids["bob"] = alice, bob
    ids["sole"] = study("sole", [one])
    ids["mixed"] = study("mixed", [one, two])
    ids["unjudged"] = study("unjudged", [three])
    ids["published"] = study("published", [four], published_judgments={four: signed})
    session.commit()

    yield ids

    study_ids = [ids[k] for k in ("sole", "mixed", "unjudged", "published")]
    session.execute(
        text("DELETE FROM study_reports WHERE study_id = ANY(:ids)"), {"ids": study_ids}
    )
    session.execute(
        text("DELETE FROM study_dataset WHERE study_id = ANY(:ids)"), {"ids": study_ids}
    )
    session.execute(text("DELETE FROM studies WHERE id = ANY(:ids)"), {"ids": study_ids})
    session.execute(
        text(
            "DELETE FROM quality_judgments WHERE evaluation_id IN "
            "(SELECT id FROM evaluations WHERE assessor_id = ANY(:ids))"
        ),
        {"ids": [alice, bob]},
    )
    session.execute(
        text("DELETE FROM evaluations WHERE assessor_id = ANY(:ids)"), {"ids": [alice, bob]}
    )
    session.execute(
        text("DELETE FROM contents WHERE id = ANY(:ids)"), {"ids": [one, two, three, four]}
    )
    session.execute(text("DELETE FROM assessors WHERE id = ANY(:ids)"), {"ids": [alice, bob]})
    session.execute(text("DELETE FROM instrument_versions WHERE id = :id"), {"id": version_id})
    session.commit()


def _pins(session, world):
    rows = session.execute(
        text("SELECT id, assessor_id FROM studies WHERE id = ANY(:ids)"),
        {"ids": [world[k] for k in ("sole", "mixed", "unjudged", "published")]},
    ).all()
    by_id = {row.id: row.assessor_id for row in rows}
    return {key: by_id[world[key]] for key in ("sole", "mixed", "unjudged", "published")}


def test_the_backfill_pins_only_where_the_author_is_unambiguous(session, world):
    session.execute(text(_backfill_sql()))
    session.commit()

    pins = _pins(session, world)
    assert pins["sole"] == world["alice"]
    # Two judges: there is no answer, and choosing one would disown the other's judgments.
    assert pins["mixed"] is None
    assert pins["unjudged"] is None


def test_a_published_study_is_pinned_to_the_author_its_report_recorded(session, world):
    """Not to whoever judged that course most recently. A published study is read through
    the judgments its frozen report named (ADR-0041 §6), so pinning the later author would
    make every read of it filter out the very judgments the document is composed from."""
    session.execute(text(_backfill_sql()))
    session.commit()

    assert _pins(session, world)["published"] == world["alice"]


def test_the_backfill_is_idempotent(session, world):
    session.execute(text(_backfill_sql()))
    session.commit()
    first = _pins(session, world)

    session.execute(text(_backfill_sql()))
    session.commit()

    assert _pins(session, world) == first
