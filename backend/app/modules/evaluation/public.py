"""Public surface of Evaluation (ARCHITECTURE.md §3).

What crosses this boundary: the human **event** `EvaluationSubmitted` (Orchestration's
completion policy consumes it), the automated-path events `EvaluationCompleted`,
`QualityJudgmentPublished` and `FindingRaised` (coordinates only — subscribers read via
the queries), and the **read side** — scores for Reporting (ADR-0006) plus the batch
judgment/finding/criterion-outcome queries Evaluation Studies composes from (13-code §3.6,
ADR-0023).
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.evaluation.application import queries as _queries
from app.modules.evaluation.application.dtos import (
    CriterionOutcomeDTO,
    CriterionScoreDTO,
    EvaluationDTO,
    FindingDTO,
    JudgmentClaimDTO,
    QualityJudgmentDTO,
    RatificationDTO,
)
from app.modules.evaluation.infrastructure.repository import (
    SqlAlchemyEvaluationRepository,
    SqlAlchemyJudgmentRepository,
    SqlAlchemyRatificationRepository,
)
from app.platform.uow import UnitOfWork, get_uow

EVALUATION_SUBMITTED = "EvaluationSubmitted"
EVALUATION_COMPLETED = "EvaluationCompleted"
QUALITY_JUDGMENT_PUBLISHED = "QualityJudgmentPublished"
FINDING_RAISED = "FindingRaised"

__all__ = [
    "EVALUATION_COMPLETED",
    "EVALUATION_SUBMITTED",
    "FINDING_RAISED",
    "QUALITY_JUDGMENT_PUBLISHED",
    "CriterionOutcomeDTO",
    "CriterionScoreDTO",
    "EvaluationCompletedFact",
    "EvaluationDTO",
    "EvaluationQueries",
    "EvaluationSubmittedFact",
    "FindingDTO",
    "FindingRaisedFact",
    "JudgmentClaimDTO",
    "QualityJudgmentDTO",
    "QualityJudgmentPublishedFact",
    "RatificationDTO",
    "get_evaluation_queries",
]


@dataclass(frozen=True)
class EvaluationSubmittedFact:
    """The Published Language of `EvaluationSubmitted` — what subscribers may rely on."""

    evaluation_id: UUID
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    mode: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EvaluationSubmittedFact":
        return cls(
            evaluation_id=UUID(payload["evaluationId"]),
            assessor_id=UUID(payload["assessorId"]),
            content_id=UUID(payload["contentId"]),
            # Old rows in `events` carry the pre-rename key; both replay fine.
            instrument_version_id=payload.get("instrumentVersionId") or payload["rubricVersionId"],
            mode=payload.get("mode", "human"),
        )


@dataclass(frozen=True)
class EvaluationCompletedFact:
    """Published Language of `EvaluationCompleted` — coordinates of one automated act."""

    evaluation_id: UUID
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    profile_id: UUID

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EvaluationCompletedFact":
        return cls(
            evaluation_id=UUID(payload["evaluationId"]),
            assessor_id=UUID(payload["assessorId"]),
            content_id=UUID(payload["contentId"]),
            instrument_version_id=payload["instrumentVersionId"],
            profile_id=UUID(payload["profileId"]),
        )


@dataclass(frozen=True)
class QualityJudgmentPublishedFact:
    judgment_id: UUID
    evaluation_id: UUID
    content_id: UUID
    instrument_version_id: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "QualityJudgmentPublishedFact":
        return cls(
            judgment_id=UUID(payload["judgmentId"]),
            evaluation_id=UUID(payload["evaluationId"]),
            content_id=UUID(payload["contentId"]),
            instrument_version_id=payload["instrumentVersionId"],
        )


@dataclass(frozen=True)
class FindingRaisedFact:
    finding_id: UUID
    judgment_id: UUID
    content_id: UUID
    claim_id: str
    criterion_id: str
    failure_mode: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FindingRaisedFact":
        return cls(
            finding_id=UUID(payload["findingId"]),
            judgment_id=UUID(payload["judgmentId"]),
            content_id=UUID(payload["contentId"]),
            claim_id=payload["claimId"],
            criterion_id=payload["criterionId"],
            failure_mode=payload["failureMode"],
        )


class EvaluationQueries:
    """Read-only contract of Evaluation."""

    def __init__(self, session: Session) -> None:
        self._evaluations = SqlAlchemyEvaluationRepository(session)
        self._judgments = SqlAlchemyJudgmentRepository(session)
        self._ratifications = SqlAlchemyRatificationRepository(session)

    def list_for_contents(self, content_ids: list[UUID]) -> list[EvaluationDTO]:
        """Every evaluation of those contents, scores included. Batch (ADR-0006)."""
        return _queries.list_evaluations_for_contents(self._evaluations, content_ids)

    def get_judgments(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[QualityJudgmentDTO]:
        """Append-only; the most recent per content is the current one. Batch."""
        return self._judgments.list_for_contents(content_ids, instrument_version_id)

    def get_criterion_outcomes(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[CriterionOutcomeDTO]:
        """The five states per criterion behind those judgments. Batch.

        The judgments' own `evidence_basis` counts the same states per claim; this is the
        un-aggregated form, for consumers that must attribute a criterion somewhere other
        than to its claim (ADR-0023).
        """
        return self._judgments.list_criterion_outcomes_for_contents(
            content_ids, instrument_version_id
        )

    def get_findings(self, content_ids: list[UUID], instrument_version_id: str) -> list[FindingDTO]:
        return self._judgments.list_findings_for_contents(content_ids, instrument_version_id)

    def list_ratifications(self, instrument_version_id: str) -> list[RatificationDTO]:
        """Who may evaluate with that version (ADR-0019) — readiness reads this."""
        return self._ratifications.list_for_instrument(instrument_version_id)

    def list_ratifications_by_assessors(self, assessor_ids: list[UUID]) -> list[RatificationDTO]:
        """The same relation read the other way: what those assessors have ratified.

        The assessors page asks this — which versions of a package's lineage it may
        already evaluate, and which are still waiting on the human act.
        """
        return self._ratifications.list_for_assessors(assessor_ids)


def get_evaluation_queries(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> EvaluationQueries:
    return EvaluationQueries(uow.session)
