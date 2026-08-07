"""Brief intake — hash identity for mechanically derived briefs (ADR-0022).

- `generation_briefs.brief_hash` records `sha256(description + materialsHash)`: the identity
  of the effective instruction. UNIQUE makes pairing a database invariant — two concurrent
  registrations of the same commission cannot mint two briefs. Nullable: manually registered
  briefs carry no hash.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_briefs", sa.Column("brief_hash", sa.Text(), nullable=True))
    op.create_unique_constraint(
        "uq_generation_briefs_brief_hash", "generation_briefs", ["brief_hash"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_generation_briefs_brief_hash", "generation_briefs", type_="unique")
    op.drop_column("generation_briefs", "brief_hash")
