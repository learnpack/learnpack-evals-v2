"""Content identity by content (ADR-0027).

`contents.version` is declarative (ADR-0005): nothing detected that the bytes behind a
registered version changed. Discovery now hashes what it fetches, and this column stores it
so re-imports dedupe and drift is refused instead of silent. Nullable on purpose: rows
registered by hand — including every row that predates this migration — carry no hash and
keep deduping by declared identity only.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("content_hash", sa.Text(), nullable=True))
    # The dedupe lookup: same logical content, same bytes → the registered no-op path.
    op.create_index(
        "ix_contents_logical_hash",
        "contents",
        ["package_format", "external_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_contents_logical_hash", table_name="contents")
    op.drop_column("contents", "content_hash")
