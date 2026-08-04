"""SQLAlchemy adapter for `GoldenReferenceRepositoryPort`."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.golden_dataset.domain.golden_dataset import GoldenReference


class SqlAlchemyGoldenReferenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, campaign_id: UUID, instrument_version_id: str) -> GoldenReference | None:
        row = (
            self._session.execute(
                text(
                    """
                    SELECT campaign_id, instrument_version_id, coverage, established_at
                      FROM golden_references
                     WHERE campaign_id = :campaign_id AND instrument_version_id = :rubric
                    """
                ),
                {"campaign_id": campaign_id, "rubric": instrument_version_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return GoldenReference(
            campaign_id=row["campaign_id"],
            instrument_version_id=row["instrument_version_id"],
            coverage=float(row["coverage"]),
            established_at=row["established_at"],
        )

    def record(self, reference: GoldenReference) -> bool:
        """Idempotent: False when this reference was already established (ADR-0003)."""
        result = self._session.execute(
            text(
                """
                INSERT INTO golden_references
                    (campaign_id, instrument_version_id, coverage)
                VALUES (:campaign_id, :rubric, :coverage)
                ON CONFLICT (campaign_id, instrument_version_id) DO NOTHING
                """
            ),
            {
                "campaign_id": reference.campaign_id,
                "rubric": reference.instrument_version_id,
                "coverage": reference.coverage,
            },
        )
        return result.rowcount > 0
