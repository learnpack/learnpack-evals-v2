"""Evaluation Studies — the thin study lifecycle (13-code §3.6).

- `studies` holds the round with a purpose: declared → prepared → open → published.
  `instrument_version_id` stays null until `PinInstrument` — pinned ONCE, before opening.
- `study_recipe` is the recipe (briefIds); `study_dataset` the dataset materialized at open.
- `study_reports` is the report composed at publish via query ports (ADR-0006 style, no
  subscription projection) and materialized immutable; it records the judgment ids used.
  It never carries a cross-claim aggregate (ADR-0011).
- Cross-module columns (`brief_id`, `content_id`, `instrument_version_id`, `published_by`)
  are deliberately FK-free — app-level referential validation (13-code §2 pattern).

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "studies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="declared"),
        sa.Column("instrument_version_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("opened_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('declared', 'prepared', 'open', 'published')",
            name="ck_studies_status",
        ),
    )
    op.create_table(
        "study_recipe",
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    op.create_table(
        "study_dataset",
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), primary_key=True),
    )
    op.create_table(
        "study_reports",
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("study_reports")
    op.drop_table("study_dataset")
    op.drop_table("study_recipe")
    op.drop_table("studies")
