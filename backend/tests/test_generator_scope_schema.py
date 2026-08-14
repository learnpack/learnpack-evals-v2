"""What migration 0021 leaves behind (ADR-0044 §13).

The backfill itself is one statement and the suite migrates an empty database, so there is
nothing for it to fill here. What IS worth pinning is the shape it leaves, because that is
the clause with a failure mode: the column carried a `server_default` of `'all'` for exactly
as long as it took to state a fact about the rows that already existed, and if one ever
survives, an insert that forgets the column means "every version" **silently** — which is the
defect this whole decision closes, one layer down.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.platform.db import SessionLocal


def test_the_column_defaults_to_nothing_and_admits_the_undeclared_draft(session):
    default, nullable = session.execute(
        text(
            """
            SELECT column_default, is_nullable
              FROM information_schema.columns
             WHERE table_name = 'studies' AND column_name = 'generator_scope'
            """
        )
    ).one()
    assert default is None, "a surviving default would make an omitted scope mean 'all'"
    # Null is the third state and belongs to drafts: `open()` is what refuses it.
    assert nullable == "YES"

    study_id = uuid4()
    session.execute(
        text("INSERT INTO studies (id, name, status) VALUES (:id, 'schema probe', 'declared')"),
        {"id": study_id},
    )
    stored = session.execute(
        text("SELECT generator_scope FROM studies WHERE id = :id"), {"id": study_id}
    ).scalar_one()
    assert stored is None
    session.execute(text("DELETE FROM studies WHERE id = :id"), {"id": study_id})
    session.commit()


def test_the_column_admits_two_values_and_no_third():
    """Its own session: a violated CHECK aborts the transaction it happens in."""
    with SessionLocal() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO studies (id, name, status, generator_scope) "
                    "VALUES (:id, 'schema probe', 'declared', 'everything')"
                ),
                {"id": uuid4()},
            )
        s.rollback()

    for value in ("all", "listed"):
        with SessionLocal() as s:
            study_id = uuid4()
            s.execute(
                text(
                    "INSERT INTO studies (id, name, status, generator_scope) "
                    "VALUES (:id, 'schema probe', 'declared', :scope)"
                ),
                {"id": study_id, "scope": value},
            )
            s.execute(text("DELETE FROM studies WHERE id = :id"), {"id": study_id})
            s.commit()
