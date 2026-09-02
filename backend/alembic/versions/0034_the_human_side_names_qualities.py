"""The human reference instrument's items are named by the quality they ask about (ADR-0062).

ADR-0052 made the item's id *be* a `qualityId` — "the id is the join", a primary key rather
than a lookup. The value moved; the name did not. `criterion` stayed on from slice 1, when
the automated path did not exist, and it now names two different things: a Likert item about
one quality, and a verifiable condition with a written `pass_condition` (ADR-0010).

The collision is about to be load-bearing. The calibration ADR-0015 §4 asks for joins these
two halves — `criterion_scores` against `judgment_claims` — so the column a reader must
understand first is the one whose name lies about what it holds.

`qualities` goes with it. Every item stored `criterion_id` and `qualities = [criterion_id]`,
the same value twice, true of all twelve items by construction rather than coincidence. The
downgrade rebuilds it exactly, which is what makes dropping it a rename and not a loss.

Constraints are renamed, not left behind. Postgres keeps a constraint's name when its table
or column is renamed, so without this the tables would carry `criteria_pkey` and
`ck_criterion_scores_range` — and migration 0029 proves this repository addresses constraints
by name.

Available only now, and the argument is 0029's own: no campaign has run, so these tables hold
no answered data anywhere but on a developer's machine. After the first campaign, renaming
what people were asked would be rewriting the record.

Revision ID: 0034
Revises: 0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table it now lives on, old name, new name). Primary keys carry their index with them.
CONSTRAINTS = (
    ("rubric_items", "criteria_pkey", "rubric_items_pkey"),
    (
        "rubric_items",
        "criteria_rubric_version_id_fkey",
        "rubric_items_rubric_version_id_fkey",
    ),
    ("item_scores", "criterion_scores_pkey", "item_scores_pkey"),
    (
        "item_scores",
        "criterion_scores_evaluation_id_fkey",
        "item_scores_evaluation_id_fkey",
    ),
    ("item_scores", "ck_criterion_scores_range", "ck_item_scores_range"),
)


def _rename_constraints(reverse: bool = False) -> None:
    for table, old, new in CONSTRAINTS:
        source, target = (new, old) if reverse else (old, new)
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {source} TO {target}")


def upgrade() -> None:
    op.rename_table("criteria", "rubric_items")
    op.rename_table("criterion_scores", "item_scores")
    op.alter_column("rubric_items", "criterion_id", new_column_name="quality_id")
    op.alter_column("item_scores", "criterion_id", new_column_name="quality_id")
    _rename_constraints()
    # The duplicate goes last: the column it duplicated has to exist under its new name
    # before this is a statement about `quality_id` rather than about `criterion_id`.
    op.drop_column("rubric_items", "qualities")


def downgrade() -> None:
    op.add_column("rubric_items", sa.Column("qualities", postgresql.JSONB(), nullable=True))
    op.execute("UPDATE rubric_items SET qualities = to_jsonb(array[quality_id])")
    op.alter_column("rubric_items", "qualities", nullable=False)
    _rename_constraints(reverse=True)
    op.alter_column("item_scores", "quality_id", new_column_name="criterion_id")
    op.alter_column("rubric_items", "quality_id", new_column_name="criterion_id")
    op.rename_table("item_scores", "criterion_scores")
    op.rename_table("rubric_items", "criteria")
