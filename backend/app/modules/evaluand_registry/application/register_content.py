"""RegisterContent → ContentVersionRegistered (02-discover.md phase 1, 08-code.md §5)."""

from dataclasses import dataclass, field
from typing import Any

from app.modules.evaluand_registry.application.ports import (
    ContentRepositoryPort,
    MetadataSchemaRepositoryPort,
)
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION, EducationalContent
from app.modules.evaluand_registry.domain.metadata import ContentMetadata, MetadataSchema
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class DuplicateContent(Exception):
    """A content version with the same (packageFormat, externalId, version) exists."""


class UnknownPackageFormat(Exception):
    """No MetadataSchema is registered for this package format."""


@dataclass(frozen=True)
class RegisterContentCommand:
    package_format: str
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)


class RegisterContent:
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

    def __call__(self, command: RegisterContentCommand) -> EducationalContent:
        schema = self._require_schema(command.package_format)

        if self._contents.exists(command.package_format, command.external_id, command.version):
            raise DuplicateContent(
                f"{command.package_format}/{command.external_id} "
                f"version {command.version} is already registered"
            )

        content = EducationalContent(
            id=new_id(),
            package_format=command.package_format,
            external_id=command.external_id,
            consumable_url=command.consumable_url,
            version=command.version,
            metadata=ContentMetadata.validated(command.metadata, schema),
        )

        self._contents.add(content)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.content_version_registered(content))
        self._uow.commit()
        return content

    def _require_schema(self, package_format: str) -> MetadataSchema:
        schema = self._schemas.get(package_format)
        if schema is None:
            raise UnknownPackageFormat(
                f"no metadata schema registered for '{package_format}'"
            )
        return schema
