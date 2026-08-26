"""A campaign is named, and its name is correctable (ADR-0055).

`name` is required; `description` is not, and nothing backfills it — an absent description is
absent (ADR-0043).

Existing rows are backfilled with `Campaign <first 8 of the id>`. That invents nothing: it is
the string the console has been displaying for those campaigns all along, promoted from a
rendering accident to a value somebody can now correct.

The check constraint mirrors the aggregate's invariant, so a blank name is refused in the two
places that can refuse it. There is no unique index: the id identifies, the name describes.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("campaigns", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE campaigns SET name = 'Campaign ' || left(id::text, 8) WHERE name IS NULL")
    op.alter_column("campaigns", "name", nullable=False)
    op.create_check_constraint("ck_campaigns_name_not_blank", "campaigns", "btrim(name) <> ''")


def downgrade() -> None:
    op.drop_constraint("ck_campaigns_name_not_blank", "campaigns", type_="check")
    op.drop_column("campaigns", "description")
    op.drop_column("campaigns", "name")
