"""Automated evaluation — the block-6 schema (13-code §3.1/§3.5, amended by ADR-0018/0019/0021).

- `assessors` learns the `human | automated` axis (ADR-0016): automated assessors are
  software artifacts identified by (name, version) inside `source_config` — no Clerk
  credential; the partial unique index is their identity guard.
- `evaluations.profile_id`: the automated path evaluates a profile, never raw content
  (ADR-0015 prerequisite); null on the legacy human path.
- `criterion_outcomes`: one row per criterion of the pinned instrument version, five
  outcomes (ADR-0018). `derived` records the outcome's origin (ADR-0021): mechanical
  derivation vs an executor that looked at evidence — pass is always executed and quoted;
  fail is quoted OR derived (the absence IS the defect, ADR-0009 §4).
- `quality_judgments.evaluation_id` UNIQUE is the idempotence key of the judgment policy
  (conditional insert, ADR-0003 pattern); judgments stay append-only per
  (content, instrument) — the most recent is the current one.
- `assessor_ratifications` (ADR-0019): the explicit act that makes an instrument version
  evaluable by an assessor; the table is the record of the act (actor + date).

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- assessors: the human | automated axis (13-code §3.1, ADR-0016/0019) ---
    op.alter_column("assessors", "clerk_user_id", nullable=True)
    op.add_column(
        "assessors",
        sa.Column("kind", sa.Text(), nullable=False, server_default="human"),
    )
    op.add_column("assessors", sa.Column("source_config", postgresql.JSONB()))
    op.create_check_constraint(
        "ck_assessors_kind", "assessors", "kind in ('human','automated')"
    )
    op.create_check_constraint(
        "ck_assessors_kind_shape",
        "assessors",
        "(kind = 'human' and clerk_user_id is not null) or "
        "(kind = 'automated' and source_config is not null and clerk_user_id is null)",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_assessors_automated_identity ON assessors "
        "((source_config->>'name'), (source_config->>'version')) WHERE kind = 'automated'"
    )

    # --- evaluations: the automated path evaluates a profile ---
    op.add_column(
        "evaluations",
        sa.Column(
            "profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_profiles.id")
        ),
    )

    # --- criterion_outcomes: five states + origin (ADR-0018/0021) ---
    op.create_table(
        "criterion_outcomes",
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("criterion_id", sa.Text(), primary_key=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("derived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("quote", sa.Text()),
        sa.Column("locator", postgresql.JSONB()),
        sa.Column("failure_mode", sa.Text()),
        sa.Column("comment", sa.Text()),
        sa.CheckConstraint(
            "outcome in ('pass','fail','not_applicable','no_evidence','not_assessed')",
            name="ck_criterion_outcomes_outcome",
        ),
        # A pass is always someone affirming something they saw (ADR-0021).
        sa.CheckConstraint(
            "outcome <> 'pass' or (quote is not null and not derived)",
            name="ck_criterion_outcomes_pass_quoted",
        ),
        # A fail is quoted, unless derived from absence — the absence IS the defect.
        sa.CheckConstraint(
            "outcome <> 'fail' or derived or quote is not null",
            name="ck_criterion_outcomes_fail_quoted_or_derived",
        ),
        sa.CheckConstraint(
            "failure_mode is null or outcome = 'fail'",
            name="ck_criterion_outcomes_failure_mode_on_fail",
        ),
    )

    # --- computed_metrics: raw measurements, rows not events (DP19) ---
    op.create_table(
        "computed_metrics",
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("metric_id", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
    )

    # --- quality_judgments + claims + findings ---
    op.create_table(
        "quality_judgments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,  # idempotence of the derivation policy (conditional insert)
        ),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_version_id", sa.Text(), nullable=False),
        sa.Column("derived_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
    )
    op.create_index(
        "ix_quality_judgments_content",
        "quality_judgments",
        ["content_id", "instrument_version_id"],
    )
    op.create_table(
        "judgment_claims",
        sa.Column(
            "judgment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quality_judgments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("claim_id", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("evidence_basis", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "status in ('supported','refuted','insufficient')",
            name="ck_judgment_claims_status",
        ),
    )
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "judgment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quality_judgments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_id", sa.Text(), nullable=False),
        sa.Column("criterion_id", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text()),  # null only on absence-derived fails (ADR-0021)
        sa.Column("locator", postgresql.JSONB()),
        sa.Column("failure_mode", sa.Text(), nullable=False),
        sa.Column("raised_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # --- assessor_ratifications (ADR-0019): the act that makes a version evaluable ---
    op.create_table(
        "assessor_ratifications",
        sa.Column(
            "assessor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessors.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "instrument_version_id",
            sa.Text(),
            sa.ForeignKey("instrument_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "ratified_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessors.id"),
            nullable=False,
        ),
        sa.Column("ratified_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("assessor_ratifications")
    op.drop_table("findings")
    op.drop_table("judgment_claims")
    op.drop_index("ix_quality_judgments_content", table_name="quality_judgments")
    op.drop_table("quality_judgments")
    op.drop_table("computed_metrics")
    op.drop_table("criterion_outcomes")
    op.drop_column("evaluations", "profile_id")
    op.execute("DROP INDEX uq_assessors_automated_identity")
    op.drop_constraint("ck_assessors_kind_shape", "assessors")
    op.drop_constraint("ck_assessors_kind", "assessors")
    op.drop_column("assessors", "source_config")
    op.drop_column("assessors", "kind")
    op.alter_column("assessors", "clerk_user_id", nullable=False)
