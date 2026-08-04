"""Evaluand registry expansion — the examinee and its products.

Realizes docs/design/13-code-qa.md §3.2: `GeneratorVersion` (declared identity of the
examinee, immutable), `GenerationBrief` (the assignment, key of paired design),
`ContentPackage` artifacts ({kind, locator, format}, kind deliberately open — no enum),
generator-level artifacts (registered, not profiled) and edit provenance on contents.
`brief_id`/`generator_version_id` are nullable: absent brief = recorded absent; null
generator = unknown, excluded from generator-level accumulation.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generator_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version", name="uq_generator_versions_identity"),
    )
    op.create_table(
        "generation_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column(
            "fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "generator_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generator_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generator_versions.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("format", sa.Text()),
        sa.Column("registered_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
    op.add_column(
        "contents",
        sa.Column("brief_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("generation_briefs.id")),
    )
    op.add_column(
        "contents",
        sa.Column(
            "generator_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generator_versions.id"),
        ),
    )
    op.add_column(
        "contents",
        sa.Column("edit_provenance", sa.Text(), nullable=False, server_default="unknown"),
    )
    op.create_check_constraint(
        "ck_contents_edit_provenance",
        "contents",
        "edit_provenance in ('pure','human_edited','unknown')",
    )
    op.create_table(
        "content_package_artifacts",
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ord", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("format", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("content_package_artifacts")
    op.drop_constraint("ck_contents_edit_provenance", "contents")
    op.drop_column("contents", "edit_provenance")
    op.drop_column("contents", "generator_version_id")
    op.drop_column("contents", "brief_id")
    op.drop_table("generator_artifacts")
    op.drop_table("generation_briefs")
    op.drop_table("generator_versions")
