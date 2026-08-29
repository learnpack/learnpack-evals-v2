"""SQLAlchemy adapters for Orchestration's ports."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orchestration.domain.assignment import Assignment
from app.modules.orchestration.domain.campaign import EvaluationCampaign

_ASSIGNMENT_COLUMNS = "id, campaign_id, content_id, assessor_id, status, created_at, updated_at"


class SqlAlchemyCampaignRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _hydrate(self, row) -> EvaluationCampaign:  # noqa: ANN001 — RowMapping
        content_ids = (
            self._session.execute(
                text("SELECT content_id FROM campaign_contents WHERE campaign_id = :id"),
                {"id": row["id"]},
            )
            .scalars()
            .all()
        )
        return EvaluationCampaign(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            instrument_version_id=row["instrument_version_id"],
            required_evaluations_per_content=row["required_evaluations_per_content"],
            dataset_version_id=row["dataset_version_id"],
            content_ids=list(content_ids),
            golden_coverage_threshold=float(row["golden_coverage_threshold"]),
            status=row["status"],
        )

    def get(self, campaign_id: UUID) -> EvaluationCampaign | None:
        row = (
            self._session.execute(
                text(
                    """
                    SELECT id, name, description, instrument_version_id,
                           required_evaluations_per_content, golden_coverage_threshold, status,
                           dataset_version_id
                      FROM campaigns WHERE id = :id
                    """
                ),
                {"id": campaign_id},
            )
            .mappings()
            .first()
        )
        return None if row is None else self._hydrate(row)

    def add(self, campaign: EvaluationCampaign) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO campaigns
                    (id, name, description, instrument_version_id,
                     required_evaluations_per_content, golden_coverage_threshold, status,
                     dataset_version_id)
                VALUES (:id, :name, :description, :rubric, :required, :threshold, :status,
                        :dataset_version_id)
                """
            ),
            {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "rubric": campaign.instrument_version_id,
                "required": campaign.required_evaluations_per_content,
                "threshold": campaign.golden_coverage_threshold,
                "status": str(campaign.status),
                "dataset_version_id": campaign.dataset_version_id,
            },
        )
        for content_id in campaign.content_ids:
            self._session.execute(
                text(
                    """
                    INSERT INTO campaign_contents (campaign_id, content_id)
                    VALUES (:campaign_id, :content_id)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"campaign_id": campaign.id, "content_id": content_id},
            )

    def update_status(self, campaign: EvaluationCampaign) -> None:
        self._session.execute(
            text("UPDATE campaigns SET status = :status WHERE id = :id"),
            {"id": campaign.id, "status": str(campaign.status)},
        )

    def update_label(self, campaign: EvaluationCampaign) -> None:
        self._session.execute(
            text("UPDATE campaigns SET name = :name, description = :description WHERE id = :id"),
            {"id": campaign.id, "name": campaign.name, "description": campaign.description},
        )

    def list_all(self) -> list[EvaluationCampaign]:
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT id, name, description, instrument_version_id,
                           required_evaluations_per_content, golden_coverage_threshold, status,
                           dataset_version_id
                      FROM campaigns ORDER BY created_at
                    """
                )
            )
            .mappings()
            .all()
        )
        return [self._hydrate(row) for row in rows]


class SqlAlchemyAssignmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row) -> Assignment:  # noqa: ANN001 — RowMapping
        return Assignment(
            id=row["id"],
            campaign_id=row["campaign_id"],
            content_id=row["content_id"],
            assessor_id=row["assessor_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _query(self, where: str, params: dict) -> list[Assignment]:
        rows = (
            self._session.execute(
                text(f"SELECT {_ASSIGNMENT_COLUMNS} FROM assignments WHERE {where}"), params
            )
            .mappings()
            .all()
        )
        return [self._to_domain(row) for row in rows]

    def get(self, assignment_id: UUID) -> Assignment | None:
        found = self._query("id = :id", {"id": assignment_id})
        return found[0] if found else None

    def add(self, assignment: Assignment) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO assignments (id, campaign_id, content_id, assessor_id, status)
                VALUES (:id, :campaign_id, :content_id, :assessor_id, :status)
                """
            ),
            {
                "id": assignment.id,
                "campaign_id": assignment.campaign_id,
                "content_id": assignment.content_id,
                "assessor_id": assignment.assessor_id,
                "status": str(assignment.status),
            },
        )

    def save_status(self, assignment: Assignment) -> None:
        self._session.execute(
            text("UPDATE assignments SET status = :status, updated_at = now() WHERE id = :id"),
            {"id": assignment.id, "status": str(assignment.status)},
        )

    def list_pending_for_assessor(self, assessor_id: UUID) -> list[Assignment]:
        return self._query(
            "assessor_id = :a AND status IN ('assigned','opened') ORDER BY created_at",
            {"a": assessor_id},
        )

    def list_for_campaign(self, campaign_id: UUID) -> list[Assignment]:
        return self._query("campaign_id = :c ORDER BY created_at", {"c": campaign_id})

    def find_active(
        self, campaign_id: UUID, content_id: UUID, assessor_id: UUID
    ) -> Assignment | None:
        found = self._query(
            "campaign_id = :c AND content_id = :co AND assessor_id = :a AND status <> 'cancelled'",
            {"c": campaign_id, "co": content_id, "a": assessor_id},
        )
        return found[0] if found else None

    def list_open_for_assessor_and_content(
        self, assessor_id: UUID, content_id: UUID
    ) -> list[Assignment]:
        """Assignments still awaiting a submission — cancelled ones never count (ADR-0002)."""
        return self._query(
            "assessor_id = :a AND content_id = :c AND status IN ('assigned','opened')",
            {"a": assessor_id, "c": content_id},
        )

    def count_submitted(self, campaign_id: UUID, content_id: UUID) -> int:
        return self._session.execute(
            text(
                """
                SELECT count(*) FROM assignments
                 WHERE campaign_id = :c AND content_id = :co AND status = 'submitted'
                """
            ),
            {"c": campaign_id, "co": content_id},
        ).scalar_one()


class SqlAlchemyCompletionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_completion(
        self, campaign_id: UUID, content_id: UUID, instrument_version_id: str
    ) -> bool:
        """Idempotent: returns False when the completion was already recorded (ADR-0003)."""
        result = self._session.execute(
            text(
                """
                INSERT INTO content_evaluation_completions
                    (campaign_id, content_id, instrument_version_id)
                VALUES (:campaign_id, :content_id, :rubric)
                ON CONFLICT (campaign_id, content_id) DO NOTHING
                """
            ),
            {
                "campaign_id": campaign_id,
                "content_id": content_id,
                "rubric": instrument_version_id,
            },
        )
        return result.rowcount > 0
