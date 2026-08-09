"""Use case: register a content version from a package source (ADR-0027).

Composes mechanical discovery with `RegisterContentVersion` — which stays the only writer
of contents: this use case turns "a package exists at X" into the canonical registration
command, nothing more. Discovery failing means no registration (hard-failing by design);
rediscovering an already-registered, unchanged package is a reported no-op.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluand_registry.application.ports import PackageDiscoveryPort
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
    UnchangedContent,
)
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION, EducationalContent


@dataclass(frozen=True, kw_only=True)
class RegisterPackageFromSourceCommand:
    package_format: str
    source_locator: str
    # No default (ADR-0024): the caller declares a generator version or declares `unknown`
    # by passing None. Silence is not a declaration.
    generator_version_id: UUID | None
    edit_provenance: str = "unknown"
    version: str = DEFAULT_VERSION
    # Declares a deployed, human-consumable instance (ADR-0028) — not an override of a
    # discovered value. Discovery supplies one only when the root IS the deployed course (an
    # http root); a filesystem source never does, and registers without one.
    consumable_url: str | None = None


@dataclass(frozen=True)
class PackageRegistration:
    content: EducationalContent
    created: bool
    artifact_count: int


class RegisterPackageFromSource:
    def __init__(self, discovery: PackageDiscoveryPort, register: RegisterContentVersion) -> None:
        self._discovery = discovery
        self._register = register

    def __call__(self, command: RegisterPackageFromSourceCommand) -> PackageRegistration:
        discovered = self._discovery.discover(command.package_format, command.source_locator)

        # A declaration beats what discovery inferred; neither is required (ADR-0028).
        consumable_url = command.consumable_url or discovered.consumable_url

        try:
            content = self._register(
                RegisterContentVersionCommand(
                    package_format=discovered.package_format,
                    external_id=discovered.external_id,
                    consumable_url=consumable_url,
                    version=command.version,
                    artifacts=[
                        {"kind": a.kind, "locator": a.locator, "format": a.format}
                        for a in discovered.artifacts
                    ],
                    generator_version_id=command.generator_version_id,
                    edit_provenance=command.edit_provenance,
                    content_hash=discovered.content_hash,
                )
            )
        except UnchangedContent as unchanged:
            existing = unchanged.existing
            return PackageRegistration(
                content=existing, created=False, artifact_count=len(existing.package.artifacts)
            )
        return PackageRegistration(
            content=content, created=True, artifact_count=len(content.package.artifacts)
        )
