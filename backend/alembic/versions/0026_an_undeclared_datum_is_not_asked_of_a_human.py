"""An item of the human reference declares the data it is about (ADR-0053).

`criteria.required_data` carries data_requirement ids from the same demand-side namespace the
automated instrument uses (ADR-0014), under the same name and with the same meaning: the data
this item is about. What differs is the consequence — here it decides whether the item is put
to a human at all.

`criterion_scores.derived` is ADR-0021's own column, ported to the human path for the reason
it was added there: it distinguishes in data "someone judged it" from "the mechanics derived
it". Together with a nullable `score` it yields four states and needs no third column — a
judgement, an abstention, an item this format cannot declare, and an item the course could
have declared and did not.

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Empty is the honest default: an item that names no datum is asked of everybody, which
    # is what every item did until now.
    op.add_column(
        "criteria",
        sa.Column(
            "required_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "criterion_scores",
        sa.Column("derived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("criterion_scores", "derived")
    op.drop_column("criteria", "required_data")
