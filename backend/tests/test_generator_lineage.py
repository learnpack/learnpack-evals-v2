"""What migration 0017 does to pre-existing rows, and what the store now refuses (ADR-0031).

The schema half is already exercised — `conftest` runs `alembic upgrade head` once per session.
Two things it does not cover, and they are the two that can be wrong:

1. **The fold.** Rows whose names differ only in casing or surrounding whitespace become one
   lineage keeping the earliest-declared spelling, and rows that would then collide on
   `(generator_id, version)` stop the migration instead of being merged by guesswork. Both
   predicates are imported from the migration rather than restated — one source of truth, or the
   test pins a fiction.
2. **The database half of the guard.** The near-miss refusal lives in the use case and can be
   overridden; the normalized uniqueness lives in an index and cannot. That index is what holds
   when two operators register at the same moment, so it is tested against the store directly.
"""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

MIGRATION = Path(__file__).parent.parent / "alembic" / "versions" / "0017_generator_lineage.py"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0017", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the database half of the guard -------------------------------------------------------


def test_two_lineages_cannot_differ_only_in_casing_or_padding(session, unique):
    """The failure the old `UNIQUE(name, version)` allowed: `Text` compares byte for byte, so
    `Gen` and `gen` were two identities. The expression index is what ends that."""
    first, second = uuid4(), uuid4()
    session.execute(
        text("INSERT INTO generators (id, name) VALUES (:id, :name)"),
        {"id": first, "name": f"lineage-{unique}"},
    )
    session.commit()
    try:
        with pytest.raises(IntegrityError):
            session.execute(
                text("INSERT INTO generators (id, name) VALUES (:id, :name)"),
                {"id": second, "name": f"  LINEAGE-{unique.upper()}  "},
            )
            session.commit()
        session.rollback()
    finally:
        session.execute(text("DELETE FROM generators WHERE id = :id"), {"id": first})
        session.commit()


def test_a_blank_lineage_name_is_refused_by_the_store(session):
    with pytest.raises(IntegrityError):
        session.execute(
            text("INSERT INTO generators (id, name) VALUES (:id, '   ')"), {"id": uuid4()}
        )
        session.commit()
    session.rollback()


# --- the fold ------------------------------------------------------------------------------
#
# Run against a scratch pair of tables shaped like the pre-migration ones, so the real
# `generators`/`generator_versions` (and everything pointing at them) stay untouched.

SCRATCH = """
CREATE TEMPORARY TABLE generator_versions_scratch (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    version text NOT NULL,
    created_at timestamptz NOT NULL
) ON COMMIT DROP;
CREATE TEMPORARY TABLE generators_scratch (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz
) ON COMMIT DROP;
"""


@pytest.fixture
def scratch(session):
    """The pre-0017 shape, in temporary tables. The migration's SQL is re-pointed at them by
    name — the statements are the migration's own, only the tables are throwaway."""
    session.execute(text(SCRATCH))

    def _seed(rows):
        for index, (name, version) in enumerate(rows):
            session.execute(
                text(
                    "INSERT INTO generator_versions_scratch (id, name, version, created_at) "
                    "VALUES (:id, :name, :version, now() + make_interval(secs => :offset))"
                ),
                {"id": uuid4(), "name": name, "version": version, "offset": index},
            )

    yield _seed
    session.rollback()


def _scoped(sql: str) -> str:
    return sql.replace("generator_versions", "generator_versions_scratch").replace(
        "generators", "generators_scratch"
    )


def test_the_fold_keeps_the_earliest_declared_spelling(session, scratch):
    # Seeded lowercase-first on purpose: uppercase sorts first in this collation, so an
    # alphabetical rule would answer "LearnPack-Gen" and pass a weaker version of this test.
    # What the migration promises is the *original* spelling, which is the earlier row.
    scratch([("learnpack-gen", "1.0"), ("LearnPack-Gen", "2.0")])

    session.execute(text(_scoped(_migration().BACKFILL_LINEAGES)))

    lineages = session.execute(text("SELECT name FROM generators_scratch")).scalars().all()
    assert lineages == ["learnpack-gen"]


def test_the_fold_does_not_merge_names_that_differ_by_more_than_case(session, scratch):
    """A separator or a spelling difference is a different generator until a human says so —
    and that judgement belongs to the near-miss guard, which can be overridden."""
    scratch([("learnpack-gen", "1.0"), ("learnpack_gen", "1.0"), ("learnpack-generator", "1.0")])

    session.execute(text(_scoped(_migration().BACKFILL_LINEAGES)))

    lineages = session.execute(text("SELECT name FROM generators_scratch")).scalars().all()
    assert sorted(lineages) == ["learnpack-gen", "learnpack-generator", "learnpack_gen"]


def test_rows_that_would_collide_after_the_fold_are_reported_not_merged(session, scratch):
    """Same folded name AND same version: `UNIQUE(generator_id, version)` cannot hold both, and
    picking one would be the migration inventing which registration was the real one."""
    scratch([("LearnPack-Gen", "1.0"), ("learnpack-gen", "1.0"), ("other-gen", "1.0")])

    colliding = session.execute(text(_scoped(_migration().FOLDED_COLLISIONS))).all()

    assert [(row.name_key, row.version, row.rows) for row in colliding] == [
        ("learnpack-gen", "1.0", 2)
    ]


def test_nothing_collides_when_the_versions_differ(session, scratch):
    scratch([("LearnPack-Gen", "1.0"), ("learnpack-gen", "2.0")])

    assert session.execute(text(_scoped(_migration().FOLDED_COLLISIONS))).all() == []
