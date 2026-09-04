"""A human evaluation records the assignment it answers (ADR-0065).

Until now an evaluation was campaign-agnostic and its membership was reconstructed as a set
lookup over `(content_id, assessor_id)`. That made an answer unattributable to the round that
asked for it, so a later campaign's answer silently replaced an earlier campaign's — the
number a closed round reported moved because of something that happened after it.

The column is nullable and stays nullable: an automated evaluation answers no assignment, and
an evaluation with none belongs to no campaign, which is what ADR-0060 §1 already said about
the automated ones and is now a consequence rather than an exception.

No FK. `assignments` belongs to Orchestration and `evaluations` to Evaluation, and
`DATA_MODEL.md` fixes the convention for that direction: a cross-module reference without a
database constraint, the same as `evaluations.content_id`.

Nothing is backfilled, and the argument is 0034's own: no campaign has run, so these rows hold
no answered data anywhere but on a developer's machine. Inventing an attribution nobody
recorded would be worse than admitting there is none.

Revision ID: 0035
Revises: 0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evaluations",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # The campaign report reads every evaluation of its assignments, so this is the lookup
    # that replaces the old `(content_id, assessor_id)` set membership.
    op.create_index("ix_evaluations_assignment", "evaluations", ["assignment_id"])


def downgrade() -> None:
    op.drop_index("ix_evaluations_assignment", table_name="evaluations")
    op.drop_column("evaluations", "assignment_id")
