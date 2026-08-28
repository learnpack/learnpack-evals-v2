"""A dataset is a named set, and changing it is a new version (ADR-0058).

A campaign's set of courses has so far been born and died inside the act that opened it: the
ids land in `campaign_contents` and nothing can name that set, reuse it, or say that two rounds
ran on the same one. Three tables give the set an identity of its own.

`datasets` is the **concept** — the thing people talk about, whose name is a label and binds
nothing (ADR-0055's rule, and the reason there is no unique index on it: the id identifies, the
name describes). `dataset_versions` is the **frozen membership**, and `note` is `NOT NULL`
because a version whose reason nobody wrote down leaves every earlier number invalid and
uninterpretable at the same time — which is the whole cost this decision exists to avoid.

`member_set_hash` is what makes a no-op detectable: minting a version whose membership equals
the current one is refused rather than recorded, the same rule `content_hash` (ADR-0027) and
`ConsumableUrlDeclared` (ADR-0054) already apply one aggregate over. It is stored rather than
recomputed because it is also what keeps a set joinable across a rebuilt database, the property
ADR-0039 §4 bought for the brief.

`dataset_version_members.content_id` carries **no foreign key**: contents belong to another
module and cross-module references are validated in the application (DATA_MODEL §8). Within the
aggregate the two cascades are real — a version belongs to its dataset and members belong to
their version, and neither outlives its parent.

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # The admin who declared it. No FK, for the same reason every other assessor
        # reference carries none outside Identity.
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("btrim(name) <> ''", name="ck_datasets_name_not_blank"),
    )

    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 1-based and per dataset: what a person says out loud ("v2"), not a global sequence.
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("member_set_hash", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("btrim(note) <> ''", name="ck_dataset_versions_note_not_blank"),
        sa.CheckConstraint("ordinal >= 1", name="ck_dataset_versions_ordinal_positive"),
        sa.UniqueConstraint("dataset_id", "ordinal", name="uq_dataset_versions_ordinal"),
    )

    op.create_table(
        "dataset_version_members",
        sa.Column(
            "dataset_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # App-validated against the registry (no cross-module FK, DATA_MODEL §8).
        sa.Column("content_id", postgresql.UUID(as_uuid=True), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("dataset_version_members")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
