"""Content Registry's Published Language (07-define.md).

`ContentSnapshot` is what Evaluation and Orchestration consume. They never import
`content_registry.domain`.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class MetadataEntryDTO:
    key: str
    value: Any
    value_type: str


@dataclass(frozen=True)
class ContentSnapshot:
    content_id: UUID
    generating_system: str
    external_id: str
    version: str
    consumable_url: str
    metadata: list[MetadataEntryDTO]

    def filtered(self, keys: list[str] | None) -> "ContentSnapshot":
        """Restrict the metadata to a campaign's `metadataView` (ADR-0001).

        Which keys an evaluator sees varies per campaign, so the filtering happens on the
        DTO — the content itself is unchanged.
        """
        if keys is None:
            return self
        allowed = set(keys)
        return ContentSnapshot(
            content_id=self.content_id,
            generating_system=self.generating_system,
            external_id=self.external_id,
            version=self.version,
            consumable_url=self.consumable_url,
            metadata=[entry for entry in self.metadata if entry.key in allowed],
        )
