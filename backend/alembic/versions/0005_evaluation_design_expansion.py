"""Evaluation Design expansion — norm-side reference data and the Instrument aggregate.

Realizes docs/design/13-code-qa.md §3.3: `pedagogical_dimensions` / `qualities` (the stable
column of the language — claims assert about them), `data_requirements` (the demand-side
namespace, ADR-0014) and the Instrument tables (root = instrument_versions; claims, criteria
and bindings as owned rows). `rubric_versions`/`criteria` stay untouched: they store
Rubric v1, the reference instrument (ADR-0015). The ON DELETE CASCADE on instrument children
serves draft re-imports; published immutability is enforced by the domain, not the DB.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- reference data (norm side) ----------------------------------------
    op.add_column("pedagogical_frameworks", sa.Column("name", sa.Text()))
    op.add_column("pedagogical_frameworks", sa.Column("scope_note", sa.Text()))
    op.create_table(
        "pedagogical_dimensions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.create_table(
        "qualities",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("dimension_id", sa.Text(), sa.ForeignKey("pedagogical_dimensions.id")),
        sa.Column(
            "grounded_in", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
    )
    op.create_table(
        "data_requirements",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "aliases", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("value_domain", postgresql.JSONB()),
        sa.Column("grounded_in", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # --- the Instrument aggregate ------------------------------------------
    op.create_table(
        "instrument_versions",
        sa.Column("id", sa.Text(), primary_key=True),  # '{instrumentId}-{version}'
        sa.Column("instrument_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("published_by", postgresql.UUID(as_uuid=True)),
        sa.Column("revision_author", postgresql.UUID(as_uuid=True)),
        sa.Column("revision_reason", sa.Text()),
        sa.Column("assisted_by", postgresql.JSONB()),
        sa.CheckConstraint(
            "status in ('draft','published','deprecated')", name="ck_instrument_versions_status"
        ),
        sa.UniqueConstraint("instrument_id", "version", name="uq_instrument_versions_identity"),
    )
    op.create_table(
        "instrument_claims",
        sa.Column(
            "instrument_version_id",
            sa.Text(),
            sa.ForeignKey("instrument_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("claim_id", sa.Text(), primary_key=True),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("quality_ids", postgresql.JSONB(), nullable=False),
        sa.Column("warrants", postgresql.JSONB(), nullable=False),
        sa.Column("alternative_explanations", postgresql.JSONB(), nullable=False),
        sa.Column("sufficiency", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "instrument_criteria",
        sa.Column(
            "instrument_version_id",
            sa.Text(),
            sa.ForeignKey("instrument_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("criterion_id", sa.Text(), primary_key=True),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("statement", sa.Text()),
        sa.Column("pass_condition", sa.Text(), nullable=False),
        sa.Column("failure_modes", postgresql.JSONB(), nullable=False),
        sa.Column("claim_ids", postgresql.JSONB(), nullable=False),
        sa.Column("required_data", postgresql.JSONB(), nullable=False),
        sa.Column("on_missing_evidence", sa.Text(), nullable=False, server_default="no_evidence"),
        sa.Column("eligible_sources", postgresql.JSONB(), nullable=False),
        sa.Column("condition", postgresql.JSONB()),
        sa.CheckConstraint(
            "on_missing_evidence in ('no_evidence','fail')",
            name="ck_instrument_criteria_on_missing",
        ),
    )
    op.create_table(
        "instrument_bindings",
        sa.Column(
            "instrument_version_id",
            sa.Text(),
            sa.ForeignKey("instrument_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("package_format", sa.Text(), primary_key=True),
        sa.Column(
            "task_variables",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_table("instrument_bindings")
    op.drop_table("instrument_criteria")
    op.drop_table("instrument_claims")
    op.drop_table("instrument_versions")
    op.drop_table("data_requirements")
    op.drop_table("qualities")
    op.drop_table("pedagogical_dimensions")
    op.drop_column("pedagogical_frameworks", "scope_note")
    op.drop_column("pedagogical_frameworks", "name")
