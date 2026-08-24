"""A declared deployment records who declared it and when (ADR-0054).

The two columns mirror `generator_attributed_by` / `generator_attributed_at` exactly, and
mean the same thing by being null: the URL came from registration, not from a later act.
They are not a history — the outbox is, through `ConsumableUrlDeclared` with its `from` and
`to` — they are the last act, next to the value it left behind.

Nothing is backfilled. Every row that carries a URL today got it at registration, which is
precisely what null on both columns says.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column("consumable_url_declared_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "contents",
        sa.Column("consumable_url_declared_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contents", "consumable_url_declared_at")
    op.drop_column("contents", "consumable_url_declared_by")
