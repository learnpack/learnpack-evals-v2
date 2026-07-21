"""Domain event published by Golden Dataset (02-discover.md, bridge).

`GoldenReferenceEstablished` is **pivotal** and the MVP's finish line: a `set × rubricVersion`
of human results reached usable ground-truth status. Calibration `[futuro]` starts here.
"""

from app.modules.golden_dataset.domain.golden_dataset import GoldenReference
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "GoldenDataset"


def golden_reference_established(reference: GoldenReference) -> DomainEvent:
    return DomainEvent(
        event_type="GoldenReferenceEstablished",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(reference.campaign_id),
        payload={
            "campaignId": str(reference.campaign_id),
            "rubricVersionId": reference.rubric_version_id,
            "coverage": reference.coverage,
        },
    )
