"""The published instrument freezes its `quality -> dimension` map (ADR-0023 clause 8).

`claim.quality_ids` is already frozen inside the version, but `qualities.dimension_id` lives
in a global, mutable, unversioned table (migration 0005) upserted from a seed file. Without
this column, re-parenting a quality silently changes the dimension-level reading of every
study already published — the one link the pin did not protect.

The backfill is exact **only because nothing has been re-parented yet**; that window closes
the first time someone edits a `dimension_id`. It covers every row, drafts included: a draft's
map is rewritten at publish, and a column that is never null spares every reader a branch.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instrument_versions",
        sa.Column(
            "quality_dimensions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Only the qualities the instrument's claims actually reference (ADR-0023 clause 8:
    # the fitness reports what the instrument measures, not the whole vocabulary).
    op.execute(
        """
        UPDATE instrument_versions iv
           SET quality_dimensions = COALESCE(
               (
                   SELECT jsonb_object_agg(q.id, q.dimension_id)
                     FROM qualities q
                    WHERE q.dimension_id IS NOT NULL
                      AND q.id IN (
                          SELECT jsonb_array_elements_text(ic.quality_ids)
                            FROM instrument_claims ic
                           WHERE ic.instrument_version_id = iv.id
                      )
               ),
               '{}'::jsonb
           )
        """
    )


def downgrade() -> None:
    op.drop_column("instrument_versions", "quality_dimensions")
