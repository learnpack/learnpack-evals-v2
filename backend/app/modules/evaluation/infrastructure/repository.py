"""SQLAlchemy adapters for the evaluation repositories — human and automated paths."""

import json
from collections import defaultdict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.evaluation.application.dtos import (
    CriterionOutcomeDTO,
    CriterionScoreDTO,
    EvaluationDTO,
    FindingDTO,
    JudgmentClaimDTO,
    QualityJudgmentDTO,
    RatificationDTO,
)
from app.modules.evaluation.application.ports import JudgmentRecord
from app.modules.evaluation.domain.automated import AutomatedEvaluation
from app.modules.evaluation.domain.evaluation import Evaluation
from app.modules.evaluation.domain.model import CriterionOutcome


class SqlAlchemyEvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, evaluation: Evaluation) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO evaluations
                    (id, assessor_id, content_id, instrument_version_id, attempt,
                     occurred_at, submitted_at)
                VALUES (:id, :assessor_id, :content_id, :rubric, :attempt,
                        :occurred_at, :submitted_at)
                """
            ),
            {
                "id": evaluation.id,
                "assessor_id": evaluation.assessor_id,
                "content_id": evaluation.content_id,
                "rubric": evaluation.instrument_version_id,
                "attempt": evaluation.attempt,
                "occurred_at": evaluation.occurred_at,
                "submitted_at": evaluation.submitted_at,
            },
        )
        for score in evaluation.result.scores:
            self._session.execute(
                text(
                    """
                    INSERT INTO criterion_scores (evaluation_id, criterion_id, score, comment)
                    VALUES (:evaluation_id, :criterion_id, :score, :comment)
                    """
                ),
                {
                    "evaluation_id": evaluation.id,
                    "criterion_id": score.criterion_id,
                    "score": score.score,
                    "comment": score.comment,
                },
            )

    def list_for_contents(self, content_ids: list[UUID]) -> list[EvaluationDTO]:
        """Two queries regardless of how many contents — never one per content (ADR-0006)."""
        if not content_ids:
            return []

        rows = (
            self._session.execute(
                text(
                    """
                    SELECT id, assessor_id, content_id, instrument_version_id, attempt, submitted_at
                      FROM evaluations
                     WHERE content_id = ANY(:content_ids)
                     ORDER BY submitted_at, id
                    """
                ),
                {"content_ids": content_ids},
            )
            .mappings()
            .all()
        )
        if not rows:
            return []

        score_rows = (
            self._session.execute(
                text(
                    """
                    SELECT evaluation_id, criterion_id, score, comment
                      FROM criterion_scores
                     WHERE evaluation_id = ANY(:evaluation_ids)
                     ORDER BY criterion_id
                    """
                ),
                {"evaluation_ids": [row["id"] for row in rows]},
            )
            .mappings()
            .all()
        )

        by_evaluation: dict[UUID, list[CriterionScoreDTO]] = defaultdict(list)
        for score in score_rows:
            by_evaluation[score["evaluation_id"]].append(
                CriterionScoreDTO(
                    criterion_id=score["criterion_id"],
                    score=score["score"],
                    comment=score["comment"],
                )
            )

        return [
            EvaluationDTO(
                evaluation_id=row["id"],
                assessor_id=row["assessor_id"],
                content_id=row["content_id"],
                instrument_version_id=row["instrument_version_id"],
                attempt=row["attempt"],
                submitted_at=row["submitted_at"],
                scores=by_evaluation.get(row["id"], []),
            )
            for row in rows
        ]


class SqlAlchemyAutomatedEvaluationRepository:
    """The automated path: `evaluations` (with profile_id) + outcomes + metrics."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, evaluation: AutomatedEvaluation) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO evaluations
                    (id, assessor_id, content_id, instrument_version_id, profile_id,
                     attempt, occurred_at, submitted_at)
                VALUES (:id, :assessor_id, :content_id, :instrument_version_id, :profile_id,
                        :attempt, :occurred_at, :submitted_at)
                """
            ),
            {
                "id": evaluation.id,
                "assessor_id": evaluation.assessor_id,
                "content_id": evaluation.content_id,
                "instrument_version_id": evaluation.instrument_version_id,
                "profile_id": evaluation.profile_id,
                "attempt": evaluation.attempt,
                "occurred_at": evaluation.occurred_at,
                "submitted_at": evaluation.submitted_at,
            },
        )
        for outcome in evaluation.outcomes:
            self._session.execute(
                text(
                    """
                    INSERT INTO criterion_outcomes
                        (evaluation_id, criterion_id, outcome, derived, quote, locator,
                         failure_mode, comment)
                    VALUES (:evaluation_id, :criterion_id, :outcome, :derived, :quote,
                            cast(:locator as jsonb), :failure_mode, :comment)
                    """
                ),
                {
                    "evaluation_id": evaluation.id,
                    "criterion_id": outcome.criterion_id,
                    "outcome": outcome.outcome,
                    "derived": outcome.derived,
                    "quote": outcome.quote,
                    "locator": json.dumps(dict(outcome.locator)) if outcome.locator else None,
                    "failure_mode": outcome.failure_mode,
                    "comment": outcome.comment,
                },
            )
        for metric in evaluation.metrics:
            self._session.execute(
                text(
                    """
                    INSERT INTO computed_metrics (evaluation_id, metric_id, value)
                    VALUES (:evaluation_id, :metric_id, cast(:value as jsonb))
                    """
                ),
                {
                    "evaluation_id": evaluation.id,
                    "metric_id": metric.metric_id,
                    "value": json.dumps(metric.value),
                },
            )

    def next_attempt(self, assessor_id: UUID, content_id: UUID, instrument_version_id: str) -> int:
        current = self._session.execute(
            text(
                """
                SELECT coalesce(max(attempt), 0) FROM evaluations
                 WHERE assessor_id = :assessor_id AND content_id = :content_id
                   AND instrument_version_id = :instrument_version_id
                """
            ),
            {
                "assessor_id": assessor_id,
                "content_id": content_id,
                "instrument_version_id": instrument_version_id,
            },
        ).scalar_one()
        return int(current) + 1

    def get_outcomes(self, evaluation_id: UUID) -> tuple[CriterionOutcome, ...]:
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT criterion_id, outcome, derived, quote, locator, failure_mode, comment
                      FROM criterion_outcomes
                     WHERE evaluation_id = :evaluation_id
                     ORDER BY criterion_id
                    """
                ),
                {"evaluation_id": evaluation_id},
            )
            .mappings()
            .all()
        )
        return tuple(
            CriterionOutcome(
                criterion_id=row["criterion_id"],
                outcome=row["outcome"],
                derived=row["derived"],
                quote=row["quote"],
                locator=row["locator"],
                failure_mode=row["failure_mode"],
                comment=row["comment"],
            )
            for row in rows
        )


class SqlAlchemyJudgmentRepository:
    """Judgments append-only; the conditional insert on evaluation_id is the policy
    idempotence (ADR-0003 pattern)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(self, record: JudgmentRecord) -> bool:
        newly = self._session.execute(
            text(
                """
                INSERT INTO quality_judgments
                    (id, evaluation_id, content_id, instrument_version_id, coverage)
                VALUES (:id, :evaluation_id, :content_id, :instrument_version_id,
                        cast(:coverage as jsonb))
                ON CONFLICT (evaluation_id) DO NOTHING
                RETURNING 1
                """
            ),
            {
                "id": record.judgment_id,
                "evaluation_id": record.evaluation_id,
                "content_id": record.content_id,
                "instrument_version_id": record.instrument_version_id,
                "coverage": json.dumps(record.coverage),
            },
        ).scalar()
        if newly is None:
            return False
        for claim in record.claims:
            self._session.execute(
                text(
                    """
                    INSERT INTO judgment_claims (judgment_id, claim_id, status, evidence_basis)
                    VALUES (:judgment_id, :claim_id, :status, cast(:evidence_basis as jsonb))
                    """
                ),
                {
                    "judgment_id": record.judgment_id,
                    "claim_id": claim.claim_id,
                    "status": claim.status,
                    "evidence_basis": json.dumps(claim.evidence_basis),
                },
            )
        for finding_id, finding in record.findings:
            self._session.execute(
                text(
                    """
                    INSERT INTO findings
                        (id, judgment_id, claim_id, criterion_id, quote, locator, failure_mode)
                    VALUES (:id, :judgment_id, :claim_id, :criterion_id, :quote,
                            cast(:locator as jsonb), :failure_mode)
                    """
                ),
                {
                    "id": finding_id,
                    "judgment_id": record.judgment_id,
                    "claim_id": finding.claim_id,
                    "criterion_id": finding.criterion_id,
                    "quote": finding.quote,
                    "locator": json.dumps(finding.locator) if finding.locator else None,
                    "failure_mode": finding.failure_mode,
                },
            )
        return True

    def list_for_contents(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[QualityJudgmentDTO]:
        """Two queries regardless of how many contents (ADR-0006)."""
        if not content_ids:
            return []
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT id, evaluation_id, content_id, instrument_version_id,
                           derived_at, coverage
                      FROM quality_judgments
                     WHERE content_id = ANY(:content_ids)
                       AND instrument_version_id = :instrument_version_id
                     ORDER BY derived_at, id
                    """
                ),
                {"content_ids": content_ids, "instrument_version_id": instrument_version_id},
            )
            .mappings()
            .all()
        )
        if not rows:
            return []
        claim_rows = (
            self._session.execute(
                text(
                    """
                    SELECT judgment_id, claim_id, status, evidence_basis
                      FROM judgment_claims
                     WHERE judgment_id = ANY(:judgment_ids)
                     ORDER BY claim_id
                    """
                ),
                {"judgment_ids": [row["id"] for row in rows]},
            )
            .mappings()
            .all()
        )
        claims_by_judgment: dict[UUID, list[JudgmentClaimDTO]] = defaultdict(list)
        for claim in claim_rows:
            claims_by_judgment[claim["judgment_id"]].append(
                JudgmentClaimDTO(
                    claim_id=claim["claim_id"],
                    status=claim["status"],
                    evidence_basis=claim["evidence_basis"],
                )
            )
        return [
            QualityJudgmentDTO(
                judgment_id=row["id"],
                evaluation_id=row["evaluation_id"],
                content_id=row["content_id"],
                instrument_version_id=row["instrument_version_id"],
                derived_at=row["derived_at"],
                coverage=row["coverage"],
                claims=claims_by_judgment.get(row["id"], []),
            )
            for row in rows
        ]

    def list_criterion_outcomes_for_contents(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[CriterionOutcomeDTO]:
        """The outcomes behind the published judgments, one row per criterion. One query.

        `quality_judgments.evaluation_id` is unique, so the join is one-to-one: these are
        exactly the outcomes the judgment was derived from, not any other evaluation's.
        """
        if not content_ids:
            return []
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT j.id AS judgment_id, j.content_id, o.criterion_id, o.outcome,
                           o.derived
                      FROM criterion_outcomes o
                      JOIN quality_judgments j ON j.evaluation_id = o.evaluation_id
                     WHERE j.content_id = ANY(:content_ids)
                       AND j.instrument_version_id = :instrument_version_id
                     ORDER BY j.content_id, o.criterion_id
                    """
                ),
                {"content_ids": content_ids, "instrument_version_id": instrument_version_id},
            )
            .mappings()
            .all()
        )
        return [
            CriterionOutcomeDTO(
                judgment_id=row["judgment_id"],
                content_id=row["content_id"],
                criterion_id=row["criterion_id"],
                outcome=row["outcome"],
                derived=row["derived"],
            )
            for row in rows
        ]

    def list_findings_for_contents(
        self, content_ids: list[UUID], instrument_version_id: str
    ) -> list[FindingDTO]:
        if not content_ids:
            return []
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT f.id, f.judgment_id, j.content_id, f.claim_id, f.criterion_id,
                           f.quote, f.locator, f.failure_mode, f.raised_at
                      FROM findings f
                      JOIN quality_judgments j ON j.id = f.judgment_id
                     WHERE j.content_id = ANY(:content_ids)
                       AND j.instrument_version_id = :instrument_version_id
                     ORDER BY f.raised_at, f.id
                    """
                ),
                {"content_ids": content_ids, "instrument_version_id": instrument_version_id},
            )
            .mappings()
            .all()
        )
        return [
            FindingDTO(
                finding_id=row["id"],
                judgment_id=row["judgment_id"],
                content_id=row["content_id"],
                claim_id=row["claim_id"],
                criterion_id=row["criterion_id"],
                quote=row["quote"],
                locator=row["locator"],
                failure_mode=row["failure_mode"],
                raised_at=row["raised_at"],
            )
            for row in rows
        ]


class SqlAlchemyRatificationRepository:
    """The ADR-0019 act, persisted. The table IS the record — no event."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(self, assessor_id: UUID, instrument_version_id: str, ratified_by: UUID) -> bool:
        newly = self._session.execute(
            text(
                """
                INSERT INTO assessor_ratifications
                    (assessor_id, instrument_version_id, ratified_by)
                VALUES (:assessor_id, :instrument_version_id, :ratified_by)
                ON CONFLICT (assessor_id, instrument_version_id) DO NOTHING
                RETURNING 1
                """
            ),
            {
                "assessor_id": assessor_id,
                "instrument_version_id": instrument_version_id,
                "ratified_by": ratified_by,
            },
        ).scalar()
        return newly is not None

    def is_ratified(self, assessor_id: UUID, instrument_version_id: str) -> bool:
        return (
            self._session.execute(
                text(
                    """
                    SELECT 1 FROM assessor_ratifications
                     WHERE assessor_id = :assessor_id
                       AND instrument_version_id = :instrument_version_id
                    """
                ),
                {"assessor_id": assessor_id, "instrument_version_id": instrument_version_id},
            ).scalar()
            is not None
        )

    def list_for_instrument(self, instrument_version_id: str) -> list[RatificationDTO]:
        """Every ratification of that version — readiness' 'is anyone eligible?' input."""
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT assessor_id, instrument_version_id, ratified_at
                      FROM assessor_ratifications
                     WHERE instrument_version_id = :id
                     ORDER BY ratified_at
                    """
                ),
                {"id": instrument_version_id},
            )
            .mappings()
            .all()
        )
        return [
            RatificationDTO(
                assessor_id=row["assessor_id"],
                instrument_version_id=row["instrument_version_id"],
                ratified_at=row["ratified_at"],
            )
            for row in rows
        ]

    def latest_ratified(self, assessor_id: UUID, instrument_version_ids: list[str]) -> str | None:
        """Most recently ratified among the candidates (the caller resolves the lineage
        into concrete version ids via Design's public — no cross-module SQL here)."""
        if not instrument_version_ids:
            return None
        return self._session.execute(
            text(
                """
                SELECT instrument_version_id FROM assessor_ratifications
                 WHERE assessor_id = :assessor_id
                   AND instrument_version_id = ANY(:candidates)
                 ORDER BY ratified_at DESC
                 LIMIT 1
                """
            ),
            {"assessor_id": assessor_id, "candidates": instrument_version_ids},
        ).scalar()
