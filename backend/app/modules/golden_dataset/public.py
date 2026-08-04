"""Public surface of Golden Dataset (ARCHITECTURE.md §3).

`GoldenReferenceEstablished` is what Calibration `[futuro]` will subscribe to; the query is
how admin views ask "is the ground truth usable yet?".
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.golden_dataset.infrastructure.repository import (
    SqlAlchemyGoldenReferenceRepository,
)
from app.platform.uow import UnitOfWork, get_uow

GOLDEN_REFERENCE_ESTABLISHED = "GoldenReferenceEstablished"

__all__ = [
    "GOLDEN_REFERENCE_ESTABLISHED",
    "GoldenDatasetQueries",
    "GoldenReferenceDTO",
    "get_golden_dataset_queries",
]


@dataclass(frozen=True)
class GoldenReferenceDTO:
    campaign_id: UUID
    instrument_version_id: str
    coverage: float
    established_at: datetime | None


class GoldenDatasetQueries:
    """Read-only contract of Golden Dataset (`getGoldenReference`)."""

    def __init__(self, session: Session) -> None:
        self._references = SqlAlchemyGoldenReferenceRepository(session)

    def get_golden_reference(
        self, campaign_id: UUID, instrument_version_id: str
    ) -> GoldenReferenceDTO | None:
        reference = self._references.get(campaign_id, instrument_version_id)
        if reference is None:
            return None
        return GoldenReferenceDTO(
            campaign_id=reference.campaign_id,
            instrument_version_id=reference.instrument_version_id,
            coverage=reference.coverage,
            established_at=reference.established_at,
        )


def get_golden_dataset_queries(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> GoldenDatasetQueries:
    return GoldenDatasetQueries(uow.session)
