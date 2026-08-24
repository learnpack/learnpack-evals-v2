"""The human reference gains an abstention and a response format (ADR-0052).

Two independent changes, both in service of the same decision.

`criterion_scores.score` becomes nullable because layer 1 now has two different ways of
saying "no number": the bottom of the scale, which means *the course does not do this* and
must penalise like the automated side's absence-derived outcome (ADR-0021, ADR-0023 §2), and
an abstention off the scale, which means *I could not see enough of this course to judge*.
The second is a null. The existing `CHECK (score between 1 and 5)` is deliberately left
alone: in Postgres a null evaluates that predicate to null, which is not false, so it passes
unchanged and keeps guarding every value that is not null.

`rubric_versions.response_format` is what tells the evaluator screen which control to render.
It cannot be derived from anything already stored — the numeric scale of `v1` and the
agreement scale of `v2` are both 1 to 5, and the difference is what the five points mean.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("criterion_scores", "score", existing_type=sa.Integer(), nullable=True)

    # Defaulted to the shape every row already has: `Rubric v1` is numeric. A version that
    # means something else says so when it is seeded.
    op.add_column(
        "rubric_versions",
        sa.Column("response_format", sa.Text(), nullable=False, server_default="numeric"),
    )
    op.create_check_constraint(
        "ck_rubric_versions_response_format",
        "rubric_versions",
        "response_format in ('numeric','likert')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_rubric_versions_response_format", "rubric_versions")
    op.drop_column("rubric_versions", "response_format")
    # Abstentions cannot survive a column that forbids them; there is nothing to convert
    # them into that would not be a lie about who answered.
    op.execute("DELETE FROM criterion_scores WHERE score IS NULL")
    op.alter_column("criterion_scores", "score", existing_type=sa.Integer(), nullable=False)
