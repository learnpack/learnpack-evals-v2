"""Ports required by Golden Dataset. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.golden_dataset.domain.golden_dataset import GoldenReference


class GoldenReferenceRepositoryPort(Protocol):
    def get(self, campaign_id: UUID, instrument_version_id: str) -> GoldenReference | None: ...

    def record(self, reference: GoldenReference) -> bool:
        """Insert it. Returns False if already established (idempotency, ADR-0003)."""
        ...
