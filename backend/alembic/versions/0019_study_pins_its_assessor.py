"""A study pins its assessor, the way it pins its instrument (ADR-0042 §8).

`studies.assessor_id` is the third leg of the triple a study's result is defined by:
dataset × instrument version × assessor. Nullable, because studies that predate the pin
exist and are read exactly as they were.

The backfill fills it only where the answer is unambiguous — exactly one distinct author
across the judgments the study is READ THROUGH — and leaves it null otherwise. Two
populations, matching the two ways a study is read (ADR-0041 §6):

* a **published** study is read through the judgments its frozen report recorded, so its
  author comes from `report->'judgmentIdsUsed'`. Taking the latest judgments instead would
  pin whoever re-evaluated a course after publication, and then every read would filter the
  frozen document's own judgments out of view;
* any other study is read by recency, so its author comes from the current judgment per
  content — the same rule `latest_judgments` applies, tie-break included.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL = """
WITH frozen AS (
    -- What the immutable document named. One row per (study, judgment).
    SELECT r.study_id, (kv.value)::uuid AS judgment_id
      FROM study_reports r,
           LATERAL jsonb_each_text(r.report -> 'judgmentIdsUsed') AS kv
),
recent AS (
    -- The current judgment per content, for studies with no frozen report. The ORDER BY
    -- mirrors `latest_judgments` exactly, `id` compared as text like Python's sort key.
    SELECT DISTINCT ON (s.id, d.content_id) s.id AS study_id, j.id AS judgment_id
      FROM studies s
      JOIN study_dataset d ON d.study_id = s.id
      JOIN quality_judgments j
        ON j.content_id = d.content_id
       AND j.instrument_version_id = s.instrument_version_id
     WHERE s.instrument_version_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM study_reports r WHERE r.study_id = s.id)
     ORDER BY s.id, d.content_id, j.derived_at DESC, j.id::text DESC
),
in_view AS (
    SELECT * FROM frozen
    UNION ALL
    SELECT * FROM recent
),
authors AS (
    SELECT v.study_id,
           count(DISTINCT e.assessor_id) AS distinct_authors,
           min(e.assessor_id::text) AS sole_author
      FROM in_view v
      JOIN quality_judgments j ON j.id = v.judgment_id
      JOIN evaluations e ON e.id = j.evaluation_id
     GROUP BY v.study_id
)
UPDATE studies s
   SET assessor_id = a.sole_author::uuid
  FROM authors a
 WHERE a.study_id = s.id
   AND a.distinct_authors = 1
"""


def upgrade() -> None:
    op.add_column(
        "studies",
        sa.Column("assessor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessors.id")),
    )
    op.execute(BACKFILL)


def downgrade() -> None:
    op.drop_column("studies", "assessor_id")
