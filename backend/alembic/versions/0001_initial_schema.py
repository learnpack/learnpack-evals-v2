"""Initial schema — MVP human slice.

Transcribes docs/design/08-code.md §3. Names follow docs/GLOSSARY.md.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- identity ----------------------------------------------------------
    # A HumanExpert Assessor. Clerk owns authentication (ADR-0004); this row is our
    # identity for provenance.
    op.create_table(
        "assessors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clerk_user_id", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text()),
        sa.Column("display_name", sa.Text()),
        sa.Column("role", sa.Text(), nullable=False, server_default="evaluator"),
        sa.Column("expertise", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role in ('admin','evaluator')", name="ck_assessors_role"),
    )

    # --- content_registry --------------------------------------------------
    # Each row is a concrete VERSION (contentId = version); the logical content is
    # (generating_system, external_id). Metadata is an open JSONB collection validated in
    # the app against metadata_schemas — the domain never references concrete keys
    # (ADR-0001, ADR-0005).
    op.create_table(
        "contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("generating_system", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False, server_default="1"),
        sa.Column("consumable_url", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "generating_system", "external_id", "version", name="uq_contents_logical_version"
        ),
    )

    op.create_table(
        "metadata_schemas",
        sa.Column("generating_system", sa.Text(), primary_key=True),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
    )

    # --- rubric_authoring --------------------------------------------------
    op.create_table(
        "pedagogical_frameworks",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("citation", sa.Text(), nullable=False),
    )

    # A published rubric version is immutable and locked; any change means a new
    # rubricVersion (07-define.md, Rubric aggregate invariant 1).
    op.create_table(
        "rubric_versions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("rubric_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text()),
        sa.Column("scale_min", sa.Integer(), nullable=False),
        sa.Column("scale_max", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "status in ('draft','published','deprecated')", name="ck_rubric_versions_status"
        ),
        sa.UniqueConstraint("rubric_id", "version", name="uq_rubric_versions_rubric_version"),
    )

    op.create_table(
        "criteria",
        sa.Column(
            "rubric_version_id",
            sa.Text(),
            sa.ForeignKey("rubric_versions.id"),
            primary_key=True,
        ),
        sa.Column("criterion_id", sa.Text(), primary_key=True),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=False),
        sa.Column("anchor_low", sa.Text(), nullable=False),
        sa.Column("anchor_high", sa.Text(), nullable=False),
        sa.Column("qualities", postgresql.JSONB(), nullable=False),
        # Grounding is a reference (N:M), never containment — the criterion cites its
        # frameworks (GLOSSARY.md, Criteria axis).
        sa.Column("grounded_in", postgresql.JSONB(), nullable=False),
        sa.Column("eligible_sources", postgresql.JSONB(), nullable=False),
    )

    # --- orchestration (ADR-0002) ------------------------------------------
    # Open-ended aggregate: config + scope. It does NOT transactionally own assignments.
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rubric_version_id", sa.Text(), sa.ForeignKey("rubric_versions.id"), nullable=False
        ),
        sa.Column("required_evaluations_per_content", sa.Integer(), nullable=False),
        sa.Column(
            "metadata_view",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "golden_coverage_threshold",
            sa.Numeric(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status in ('draft','open','closed')", name="ck_campaigns_status"),
        sa.CheckConstraint(
            "required_evaluations_per_content >= 1", name="ck_campaigns_required_positive"
        ),
    )

    op.create_table(
        "campaign_contents",
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id"),
            primary_key=True,
        ),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id"),
            primary_key=True,
        ),
    )

    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id"),
            nullable=False,
        ),
        sa.Column(
            "assessor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessors.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="assigned"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('assigned','opened','submitted','cancelled')", name="ck_assignments_status"
        ),
    )
    # At most one ACTIVE assignment per (campaign, content, assessor). This is the unit of
    # human anti-duplication (ADR-0005) and what makes counting quorum by
    # `assignments submitted` equivalent to counting distinct assessors (ADR-0002).
    op.create_index(
        "uq_assignments_active",
        "assignments",
        ["campaign_id", "content_id", "assessor_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
    )
    op.create_index("ix_assignments_assessor_status", "assignments", ["assessor_id", "status"])

    # --- evaluation --------------------------------------------------------
    # Identity = its own id. Deliberately NO uniqueness on
    # (assessor, content, rubric_version): repetitions of the same Assessor over the same
    # (content, rubric) must coexist — e.g. an LLMJudge run N times to measure dispersion.
    # Also CAMPAIGN-AGNOSTIC: the link to a campaign is the assignment, so one evaluation
    # can satisfy several campaigns (ADR-0002, ADR-0005).
    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assessor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessors.id"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id"),
            nullable=False,
        ),
        sa.Column(
            "rubric_version_id", sa.Text(), sa.ForeignKey("rubric_versions.id"), nullable=False
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True)),
    )
    op.create_index("ix_evaluations_content", "evaluations", ["content_id", "rubric_version_id"])

    op.create_table(
        "criterion_scores",
        sa.Column(
            "evaluation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("criterion_id", sa.Text(), primary_key=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.CheckConstraint("score between 1 and 5", name="ck_criterion_scores_range"),
    )

    # --- completion (emitted by orchestration's quorum policy) --------------
    op.create_table(
        "content_evaluation_completions",
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id"),
            primary_key=True,
        ),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id"),
            primary_key=True,
        ),
        sa.Column(
            "rubric_version_id", sa.Text(), sa.ForeignKey("rubric_versions.id"), nullable=False
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # --- golden_dataset ----------------------------------------------------
    op.create_table(
        "golden_references",
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id"),
            primary_key=True,
        ),
        sa.Column(
            "rubric_version_id", sa.Text(), sa.ForeignKey("rubric_versions.id"), primary_key=True
        ),
        sa.Column("coverage", sa.Numeric(), nullable=False),
        sa.Column("established_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )

    # --- events (append-only outbox, ADR-0003) -----------------------------
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column(
            "occurred_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("dispatched_at", sa.TIMESTAMP(timezone=True)),
    )
    # Supports replay of a failed policy and idempotency by event_type + aggregate_id.
    op.create_index("ix_events_type_aggregate", "events", ["event_type", "aggregate_id"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("golden_references")
    op.drop_table("content_evaluation_completions")
    op.drop_table("criterion_scores")
    op.drop_table("evaluations")
    op.drop_table("assignments")
    op.drop_table("campaign_contents")
    op.drop_table("campaigns")
    op.drop_table("criteria")
    op.drop_table("rubric_versions")
    op.drop_table("pedagogical_frameworks")
    op.drop_table("metadata_schemas")
    op.drop_table("contents")
    op.drop_table("assessors")
