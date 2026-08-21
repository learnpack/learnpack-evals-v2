"""An assessor can leave without being erased (ADR-0051).

`assessors.status` says whether this assessor still takes part. Nothing else changes: the
judgments they produced, the assignments they answered and the reports naming them are facts
about what happened, and a person leaving the project does not unmake them — the same reason
ADR-0033 refuses to retire registered content.

**NOT NULL with a default, unlike migration 0021's deliberate absence of one.** There the
null carried meaning (a recipe nobody had declared yet); here it would not: every assessor
that exists today takes part, and an insert that forgets the column means the ordinary case
rather than a silent guess.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assessors",
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
    )
    op.create_check_constraint(
        "ck_assessors_status", "assessors", "status in ('active','deactivated')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_assessors_status", "assessors", type_="check")
    op.drop_column("assessors", "status")
