"""Migration 0015's backfill predicate (ADR-0028 §6).

The schema half of the migration is already exercised — `conftest` runs `alembic upgrade
head` once per session. What no other test covers is *which rows* the backfill touches, and
that is the only part that can be wrong: too narrow leaves a URL that 404s in front of an
evaluator, too wide destroys a real declaration. So the statement itself is imported from the
migration rather than restated here — one source of truth, or the test pins a fiction.
"""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

MIGRATION = (
    Path(__file__).parent.parent / "alembic" / "versions" / "0015_optional_consumable_url.py"
)


def _backfill_sql() -> str:
    spec = importlib.util.spec_from_file_location("migration_0015", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LOCAL_MOUNT_BACKFILL


# (label, registered URL, nulled by the backfill?)
CASES = [
    ("the dev mount", "http://localhost:8000/packages/gen@1.0.0/a-course", True),
    ("the mount by loopback ip", "http://127.0.0.1:8000/packages/gen@1.0.0/a-course", True),
    ("a real deployment", "https://a-course.learn-pack.com/", False),
    # A deployed host may legitimately serve a /packages/ path, and a local dev server may
    # legitimately host something that is not the mount. Both halves of the predicate matter.
    ("a deployed /packages/ path", "https://courses.example.com/packages/a-course", False),
    ("localhost, but not the mount", "http://localhost:3000/a-course", False),
]


@pytest.fixture
def rows(session, unique):
    """Throwaway `contents` rows, one per case, removed whatever the assertions do."""
    created = {}
    for index, (_, url, _) in enumerate(CASES):
        content_id = uuid4()
        session.execute(
            text(
                """
                INSERT INTO contents
                    (id, package_format, external_id, version, consumable_url,
                     generator_version_id, edit_provenance)
                VALUES (:id, 'LearnpackV1', :external_id, '1', :url, NULL, 'unknown')
                """
            ),
            {"id": content_id, "external_id": f"backfill-{unique}-{index}", "url": url},
        )
        created[url] = content_id
    session.commit()
    yield created
    session.execute(
        text("DELETE FROM contents WHERE id = ANY(:ids)"), {"ids": list(created.values())}
    )
    session.commit()


def _urls(session, rows):
    stored = session.execute(
        text("SELECT id, consumable_url FROM contents WHERE id = ANY(:ids)"),
        {"ids": list(rows.values())},
    ).all()
    by_id = {row.id: row.consumable_url for row in stored}
    return {url: by_id[content_id] for url, content_id in rows.items()}


def test_the_backfill_nulls_only_the_minted_mount_urls(session, rows):
    session.execute(text(_backfill_sql()))
    session.commit()

    after = _urls(session, rows)
    for label, url, nulled in CASES:
        assert (after[url] is None) is nulled, f"{label}: {url} -> {after[url]!r}"


def test_the_backfill_is_idempotent(session, rows):
    session.execute(text(_backfill_sql()))
    session.commit()
    first = _urls(session, rows)

    session.execute(text(_backfill_sql()))
    session.commit()

    assert _urls(session, rows) == first
