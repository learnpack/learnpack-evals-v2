"""The recipe declares which generator versions the round measures (ADR-0044).

`studies.generator_scope` says which of the two forms the recipe's second axis takes, and
`study_recipe_generators` holds the ids when the form is `listed`. Together they are one
value: `all` carries no rows, `listed` carries at least one.

**NULL is a third thing and only a draft may hold it**: nobody has declared yet. `open()`
refuses it (ADR-0044 §2), the way it refuses a study with no instrument — which is why the
column is nullable and has **no default at all**. A default would let an insert that forgets
the column mean "every version" silently, and that is the defect this whole decision closes,
reintroduced one layer down.

**The backfill states a fact rather than guessing one** (ADR-0044 §12). Every study that
exists had its dataset materialized with no generator filter, so `all` describes what
happened; it is not the judgement call ADR-0042's backfill had to make. Drafts are filled
too and cost nothing by it — a draft is editable by definition.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("studies", sa.Column("generator_scope", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_studies_generator_scope",
        "studies",
        "generator_scope IS NULL OR generator_scope IN ('all', 'listed')",
    )
    # Not a default: a statement about the rows that already exist, made once.
    op.execute("UPDATE studies SET generator_scope = 'all'")
    op.create_table(
        "study_recipe_generators",
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # FK-free across modules, like every other id the recipe holds (13-code §2).
        sa.Column("generator_version_id", postgresql.UUID(as_uuid=True), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("study_recipe_generators")
    op.drop_constraint("ck_studies_generator_scope", "studies", type_="check")
    op.drop_column("studies", "generator_scope")
