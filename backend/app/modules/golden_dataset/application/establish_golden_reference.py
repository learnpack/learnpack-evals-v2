"""Policy: `ContentEvaluationCompleted` → `GoldenReferenceEstablished` (08-code.md §5).

Golden Dataset does not track completions itself: it asks Orchestration for the campaign's
coverage (which Orchestration already computes) and applies its own rule. That split is the
point — coverage is a fact about the effort, usability is a judgement about the ground truth.

Idempotent, like every policy here: it may be replayed from the `events` table (ADR-0003).
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.modules.golden_dataset.application.ports import GoldenReferenceRepositoryPort
from app.modules.golden_dataset.domain import events
from app.modules.golden_dataset.domain.golden_dataset import GoldenReference, is_usable
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CampaignCoverage:
    """What Golden Dataset needs to know about a campaign — read via its query port."""

    campaign_id: UUID
    rubric_version_id: str
    coverage: float
    threshold: float


class EstablishGoldenReference:
    def __init__(
        self,
        references: GoldenReferenceRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._references = references
        self._publisher = publisher
        self._uow = uow

    def __call__(self, coverage: CampaignCoverage) -> GoldenReference | None:
        """Returns the reference when it is established *by this call*, else None."""
        if not is_usable(coverage.coverage, coverage.threshold):
            return None

        reference = GoldenReference(
            campaign_id=coverage.campaign_id,
            rubric_version_id=coverage.rubric_version_id,
            coverage=coverage.coverage,
        )
        # Publish only if we actually recorded it — replays must not re-emit the event.
        if not self._references.record(reference):
            return None

        self._publisher.publish(events.golden_reference_established(reference))
        self._uow.commit()
        logger.info(
            "golden reference established for campaign %s (coverage %.2f)",
            coverage.campaign_id,
            coverage.coverage,
        )
        return reference
