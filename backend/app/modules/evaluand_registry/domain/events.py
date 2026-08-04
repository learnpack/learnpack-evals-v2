"""Domain events published by Content Registry (02-discover.md, phase 1)."""

from app.modules.evaluand_registry.domain.content import EducationalContent
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "EducationalContent"


def content_version_registered(content: EducationalContent) -> DomainEvent:
    return DomainEvent(
        event_type="ContentVersionRegistered",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(content.id),
        payload={
            "contentId": str(content.id),
            "generatingSystem": content.generating_system,
            "externalId": content.external_id,
            "version": content.version,
            "consumableUrl": content.consumable_url,
        },
    )


def content_metadata_updated(content: EducationalContent) -> DomainEvent:
    return DomainEvent(
        event_type="ContentMetadataUpdated",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(content.id),
        payload={
            "contentId": str(content.id),
            # Keys only: the event records *that* metadata changed, and the registry stays
            # the source of truth for the values.
            "keys": sorted(content.metadata.values),
        },
    )
