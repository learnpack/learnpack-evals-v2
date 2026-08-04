"""Content Profiling — cited canonical evidence extracted from content packages.

Realizes docs/design/13-code-qa.md §3.4: `content_profiles` (root keyed by
(content_id, adapter_version) — one extraction of one content by one adapter version),
`profile_entries` (canonical entries, Conformist to the `data_requirements` namespace of
Evaluation Design; the CHECK enforces ADR-0009: a value without a verbatim quote is not
evidence — only `absent` may go quoteless), `profile_extras` (non-canonical findings, out
of contract) and `extraction_acceptances` (the human act that qualifies an adapter version
per package format, ADR-0012). An explicit `absent` entry is NOT the same as no entry:
declared capability + missing data ⇒ `absent` row (12-define invariant 3, by construction).

Profiles are immutable once `ok`; a `failed` profile is the one exception — it is never
referenced by judgments, so the manual re-profile path may replace it in place (the
unique constraint leaves no room to keep both).

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id"),
            nullable=False,
        ),
        sa.Column("package_format", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("profiled_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status in ('ok','failed')", name="ck_content_profiles_status"),
        sa.UniqueConstraint(
            "content_id", "adapter_version", name="uq_content_profiles_coordinates"
        ),
    )
    op.create_table(
        "profile_entries",
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("data_requirement_id", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB()),
        sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text()),
        sa.Column("locator", postgresql.JSONB()),
        sa.CheckConstraint(
            "provenance in ('declared_structured','declared_in_content','absent')",
            name="ck_profile_entries_provenance",
        ),
        # ADR-0009: without a quote it is not evidence.
        sa.CheckConstraint(
            "provenance = 'absent' or quote is not null",
            name="ck_profile_entries_value_requires_quote",
        ),
    )
    op.create_table(
        "profile_extras",
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("content_profiles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB()),
        sa.Column("quote", sa.Text()),
        sa.Column("locator", postgresql.JSONB()),
    )
    op.create_table(
        "extraction_acceptances",
        sa.Column("package_format", sa.Text(), primary_key=True),
        sa.Column("adapter_version", sa.Text(), primary_key=True),
        # Cross-module reference to assessors: validated at the app level, no FK
        # (same pattern as instrument_versions.published_by).
        sa.Column("accepted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accepted_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("extraction_acceptances")
    op.drop_table("profile_extras")
    op.drop_table("profile_entries")
    op.drop_table("content_profiles")
