"""The sixth outcome state — `execution_error` (ADR-0037).

- `criterion_outcomes.outcome` admits `'execution_error'`: a fact of one run's execution
  (the judge could not judge), never a verdict about the content. Minted by the
  derivation from a typed failure, below the failure budget; past the budget the
  evaluation still aborts whole and no row exists.
- `execution_cause` carries why, structured (`{task, kind, message}`), exactly when the
  outcome is `execution_error` — so a reader can tell a timeout from a degeneration loop.
- The state is always derived and quoteless (a quote belongs to a verdict); the existing
  pass/fail CHECKs are untouched because they exclude other outcomes by construction.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("criterion_outcomes", sa.Column("execution_cause", postgresql.JSONB()))
    op.drop_constraint("ck_criterion_outcomes_outcome", "criterion_outcomes")
    op.create_check_constraint(
        "ck_criterion_outcomes_outcome",
        "criterion_outcomes",
        "outcome in ('pass','fail','not_applicable','no_evidence','not_assessed',"
        "'execution_error')",
    )
    op.create_check_constraint(
        "ck_criterion_outcomes_execution_cause",
        "criterion_outcomes",
        "(outcome = 'execution_error') = (execution_cause is not null)",
    )
    op.create_check_constraint(
        "ck_criterion_outcomes_execution_error_shape",
        "criterion_outcomes",
        "outcome <> 'execution_error' or (derived and quote is null)",
    )


def downgrade() -> None:
    # Fails if any row carries the state — honest: the six-state vocabulary cannot be
    # narrowed under data that speaks it.
    op.drop_constraint("ck_criterion_outcomes_execution_error_shape", "criterion_outcomes")
    op.drop_constraint("ck_criterion_outcomes_execution_cause", "criterion_outcomes")
    op.drop_constraint("ck_criterion_outcomes_outcome", "criterion_outcomes")
    op.create_check_constraint(
        "ck_criterion_outcomes_outcome",
        "criterion_outcomes",
        "outcome in ('pass','fail','not_applicable','no_evidence','not_assessed')",
    )
    op.drop_column("criterion_outcomes", "execution_cause")
