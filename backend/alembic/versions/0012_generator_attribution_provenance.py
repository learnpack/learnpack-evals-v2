"""Late generator attribution — provenance of a discovered link (ADR-0024).

- `generator_attributed_by` / `generator_attributed_at` are set only when the link was
  filled **after** registration. Null on both means the generator was declared when the
  content was registered — the distinction matters because a reconstruction carries more
  risk than a contemporaneous declaration, and because a published study report is frozen:
  the timestamp is what lets anyone tell a report predates the attribution.
- The CHECKs turn the two invariants into structure: the pair travels together, and
  provenance cannot exist without a generator to be provenance of.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("generator_attributed_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "contents",
        sa.Column("generator_attributed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_contents_generator_attribution_pair",
        "contents",
        "(generator_attributed_by IS NULL) = (generator_attributed_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_contents_generator_attribution_needs_generator",
        "contents",
        "generator_attributed_by IS NULL OR generator_version_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_contents_generator_attribution_needs_generator", "contents")
    op.drop_constraint("ck_contents_generator_attribution_pair", "contents")
    op.drop_column("contents", "generator_attributed_at")
    op.drop_column("contents", "generator_attributed_by")
