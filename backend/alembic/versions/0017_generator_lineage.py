"""A generator is an entity; its versions belong to it (ADR-0031).

`generator_versions.name` was free text, retyped at every registration. `UNIQUE(name, version)`
protected against collision, but the failure this shape produces is the opposite one: a typo mints
an unwanted *distinction* — a version of one generator recorded as a different generator — which no
unique constraint can catch, and which was permanent because the row is immutable (ADR-0030 §3).
The lineage becomes a row of its own: the name is typed once per generator, and a version selects
it by id.

The backfill groups existing rows by `lower(btrim(name))` — the two variations a hand-typed name
produces without meaning to, and the ones the old constraint compared byte for byte, so two rows
could genuinely differ only that way. Each group keeps its earliest-declared spelling; the others
stop being queryable state and survive only inside the `GeneratorVersionRegistered` rows of the
append-only outbox. Nothing else is folded: a separator or a spelling difference is a different
generator until a human says otherwise, and that judgement belongs to the near-miss guard in the
use case, which can be overridden, not to a migration, which cannot.

`upgrade()` refuses rather than choose when two rows fold together *and* declare the same version:
`UNIQUE(generator_id, version)` is stricter than the constraint it replaces, and the only ways
through are to rename a row or drop one — a decision about which registration is the real one,
which is the operator's. Refusing in `upgrade()` is harsher than this repo's precedent (0015
refuses in `downgrade`); it is right here because the alternative is to invent that answer.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The rows the fold would merge into one `(generator_id, version)`. Read before anything is
# created, so a refusal leaves the schema exactly as it was.
# The test reads this constant rather than restating the predicate (test_generator_lineage).
FOLDED_COLLISIONS = """
SELECT lower(btrim(name)) AS name_key, version, count(*) AS rows
  FROM generator_versions
 GROUP BY 1, 2
HAVING count(*) > 1
 ORDER BY 1, 2
"""

# One lineage per folded name. The representative spelling is the earliest declared one — the
# original, not the alphabetically luckiest — so the choice is reproducible and defensible.
# `gen_random_uuid()` is built into Postgres 13+; ids come from Python everywhere else in this
# repo, but doing it there would mean pulling every folded group into the process to hand ids
# back for the same result.
BACKFILL_LINEAGES = """
INSERT INTO generators (id, name, created_at)
SELECT gen_random_uuid(),
       (array_agg(name ORDER BY created_at, id))[1],
       min(created_at)
  FROM generator_versions
 GROUP BY lower(btrim(name))
"""

LINK_VERSIONS = """
UPDATE generator_versions v
   SET generator_id = g.id
  FROM generators g
 WHERE lower(btrim(g.name)) = lower(btrim(v.name))
"""

RESTORE_NAMES = """
UPDATE generator_versions v
   SET name = g.name
  FROM generators g
 WHERE g.id = v.generator_id
"""


def upgrade() -> None:
    colliding = op.get_bind().execute(sa.text(FOLDED_COLLISIONS)).all()
    if colliding:
        listed = ", ".join(f"'{key}' {version} (x{rows})" for key, version, rows in colliding)
        raise RuntimeError(
            f"{len(colliding)} generator identity(ies) differ only in casing or surrounding "
            f"whitespace and declare the same version, so they cannot become one lineage: "
            f"{listed} — decide which registration is the real one and either rename the others "
            "(UPDATE generator_versions SET name = '<the real name>' WHERE id = '<id>') or drop "
            "them (DELETE FROM generator_versions WHERE id = '<id>'; a row with contents "
            "attached must be re-pointed first), then re-run"
        )

    op.create_table(
        "generators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        # Mirrors the domain invariant (`Generator.__post_init__`). Deliberately not a charset
        # rule: that would be a guess about the vocabulary of a free-text label (ADR-0031).
        sa.CheckConstraint("btrim(name) <> ''", name="ck_generators_name_not_blank"),
    )
    # Casing and surrounding whitespace cannot make two lineages. An expression index rather than
    # a stored key column: the normalization is a domain rule (`normalized_name`), and the
    # repository's lookup uses this same expression, so the two cannot drift apart.
    op.create_index(
        "uq_generators_name_key", "generators", [sa.text("lower(btrim(name))")], unique=True
    )
    op.execute(BACKFILL_LINEAGES)

    op.add_column(
        "generator_versions",
        sa.Column("generator_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_generator_versions_generator",
        "generator_versions",
        "generators",
        ["generator_id"],
        ["id"],
    )
    op.execute(LINK_VERSIONS)
    op.alter_column(
        "generator_versions",
        "generator_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    op.drop_constraint("uq_generator_versions_identity", "generator_versions", type_="unique")
    op.create_unique_constraint(
        "uq_generator_versions_identity", "generator_versions", ["generator_id", "version"]
    )
    op.drop_column("generator_versions", "name")


def downgrade() -> None:
    # Unlike 0015 and 0016, this one goes back with its data: the name each version carried is
    # still derivable from its lineage. Two things do not come back — a lineage with no versions
    # (a mint with no consequence; nothing referenced it), and the folding the backfill applied
    # (rows that differed only in casing come back spelled the same). Recreating
    # `UNIQUE(name, version)` is safe by construction: a unique lineage name plus
    # `UNIQUE(generator_id, version)` already implies it.
    op.add_column("generator_versions", sa.Column("name", sa.Text(), nullable=True))
    op.execute(RESTORE_NAMES)
    op.alter_column("generator_versions", "name", existing_type=sa.Text(), nullable=False)

    op.drop_constraint("uq_generator_versions_identity", "generator_versions", type_="unique")
    op.create_unique_constraint(
        "uq_generator_versions_identity", "generator_versions", ["name", "version"]
    )
    op.drop_constraint("fk_generator_versions_generator", "generator_versions", type_="foreignkey")
    op.drop_column("generator_versions", "generator_id")
    op.drop_index("uq_generators_name_key", table_name="generators")
    op.drop_table("generators")
