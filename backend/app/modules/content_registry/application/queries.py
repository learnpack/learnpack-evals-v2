"""Read-only query port of Content Registry (05-connect.md).

`getContentSnapshot` / `getContentMetadata` are how Evaluation and Orchestration read
content — never by joining against `contents` themselves (08-code.md §3, FK rule).
"""

from uuid import UUID

from app.modules.content_registry.application.dtos import ContentSnapshot, MetadataEntryDTO
from app.modules.content_registry.application.ports import (
    ContentRepositoryPort,
    MetadataSchemaRepositoryPort,
)
from app.modules.content_registry.domain.content import EducationalContent


def _to_snapshot(
    content: EducationalContent, schemas: MetadataSchemaRepositoryPort
) -> ContentSnapshot:
    schema = schemas.get(content.generating_system)
    entries = schema.entries(content.metadata.values) if schema else []
    return ContentSnapshot(
        content_id=content.id,
        generating_system=content.generating_system,
        external_id=content.external_id,
        version=content.version,
        consumable_url=content.consumable_url,
        metadata=[
            MetadataEntryDTO(key=e.key, value=e.value, value_type=str(e.value_type))
            for e in entries
        ],
    )


def get_content_snapshot(
    contents: ContentRepositoryPort,
    schemas: MetadataSchemaRepositoryPort,
    content_id: UUID,
) -> ContentSnapshot | None:
    content = contents.get_by_id(content_id)
    if content is None:
        return None
    return _to_snapshot(content, schemas)


def get_content_metadata(
    contents: ContentRepositoryPort,
    schemas: MetadataSchemaRepositoryPort,
    content_id: UUID,
) -> list[MetadataEntryDTO] | None:
    snapshot = get_content_snapshot(contents, schemas, content_id)
    return None if snapshot is None else snapshot.metadata


def list_content_snapshots(
    contents: ContentRepositoryPort, schemas: MetadataSchemaRepositoryPort
) -> list[ContentSnapshot]:
    return [_to_snapshot(content, schemas) for content in contents.list_all()]
