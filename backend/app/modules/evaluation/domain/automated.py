"""AutomatedEvaluation — the automated path's aggregate root (13-code §3.5).

A sibling of the legacy human `Evaluation` (scores 1-5), NOT an extension of it: the two
share the `evaluations` table but write different children (`criterion_outcomes` vs
`criterion_scores`) and carry different invariants. Identity per ADR-0005: its own
`evaluationId`; repetitions of the same (assessor, content, instrumentVersion) are
first-class and collapse to the most recent downstream; `attempt` counts them (max+1,
informational).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.modules.evaluation.domain.model import (
    ComputedMetric,
    CriterionOutcome,
    InstrumentSpec,
    InvalidAutomatedEvaluation,
)


@dataclass
class AutomatedEvaluation:
    """One completed automated evaluation: exact five-state coverage over one profile."""

    id: UUID
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    profile_id: UUID
    outcomes: tuple[CriterionOutcome, ...]
    metrics: tuple[ComputedMetric, ...] = ()
    attempt: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None

    @classmethod
    def complete(
        cls,
        *,
        evaluation_id: UUID,
        assessor_id: UUID,
        content_id: UUID,
        instrument: InstrumentSpec,
        profile_id: UUID,
        outcomes: tuple[CriterionOutcome, ...],
        metrics: tuple[ComputedMetric, ...] = (),
        attempt: int = 1,
    ) -> "AutomatedEvaluation":
        """Exact coverage: one outcome per criterion of the snapshot — ni falta ni sobra."""
        outcome_ids = [o.criterion_id for o in outcomes]
        if len(outcome_ids) != len(set(outcome_ids)):
            raise InvalidAutomatedEvaluation("duplicate outcomes for the same criterion")
        expected = instrument.criterion_ids
        got = frozenset(outcome_ids)
        if got != expected:
            missing = sorted(expected - got)
            beyond = sorted(got - expected)
            problems = []
            if missing:
                problems.append(f"criteria without an outcome: {', '.join(missing)}")
            if beyond:
                problems.append(f"outcomes beyond the snapshot: {', '.join(beyond)}")
            raise InvalidAutomatedEvaluation(
                "; ".join(problems) + " (exact coverage, 12-define PE invariant 1)"
            )
        if attempt < 1:
            raise InvalidAutomatedEvaluation("attempt starts at 1")
        now = datetime.now(UTC)
        return cls(
            id=evaluation_id,
            assessor_id=assessor_id,
            content_id=content_id,
            instrument_version_id=instrument.instrument_version_id,
            profile_id=profile_id,
            outcomes=outcomes,
            metrics=metrics,
            attempt=attempt,
            occurred_at=now,
            submitted_at=now,
        )
