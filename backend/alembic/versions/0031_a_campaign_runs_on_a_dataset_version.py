"""A campaign runs on a dataset version (ADR-0058 §5).

The column records **how the scope was chosen**; `campaign_contents` stays what it always was,
**what the campaign judged**. Two mechanisms and deliberately not one: the copy is what the
assignment path reads, and it is what makes the scope survive anything that happens to the set
afterwards.

Nullable, and **nothing backfills it**. The campaigns that already exist were not chosen from a
version — they were typed into a form — and inventing one would be a claim about how a past
round was composed that nobody made. It is the reading `studies.assessor_id` already gets: null
means the row predates the decision, and every read behaves as it did.

There is no foreign key. `dataset_versions` belongs to another module, and cross-module
references are validated in the application (DATA_MODEL §8) — here, by the use case, which
refuses a version the store cannot resolve.

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "dataset_version_id")
