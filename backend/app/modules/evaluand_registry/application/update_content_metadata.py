"""UpdateContentMetadata → ContentMetadataUpdated (08-code.md §5)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    ContentRepositoryPort,
    MetadataSchemaRepositoryPort,
)
from app.modules.evaluand_registry.application.register_content import UnknownPackageFormat
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class ContentNotFound(Exception):
    """No content version with that id."""


@dataclass(frozen=True)
class UpdateContentMetadataCommand:
    content_id: UUID
    metadata: dict[str, Any]


class UpdateContentMetadata:
    def __init__(
        self,
        contents: ContentRepositoryPort,
        schemas: MetadataSchemaRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._contents = contents
        self._schemas = schemas
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: UpdateContentMetadataCommand) -> EducationalContent:
        content = self._contents.get_by_id(command.content_id)
        if content is None:
            raise ContentNotFound(str(command.content_id))

        schema = self._schemas.get(content.package_format)
        if schema is None:
            raise UnknownPackageFormat(
                f"no metadata schema registered for '{content.package_format}'"
            )

        # Raises InvalidMetadata with every violation; the aggregate stays untouched.
        content.update_metadata(command.metadata, schema)

        self._contents.update_metadata(content)
        self._publisher.publish(events.content_metadata_updated(content))
        self._uow.commit()
        return content
