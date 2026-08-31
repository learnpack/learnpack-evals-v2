"""Use case: register a content version from a package source (ADR-0027).

Composes mechanical discovery with `RegisterContentVersion` — which stays the only writer
of contents: this use case turns "a package exists at X" into the canonical registration
command, nothing more. Discovery failing means no registration (hard-failing by design);
rediscovering an already-registered, unchanged package is a reported no-op.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    GeneratorRepositoryPort,
    GeneratorVersionRepositoryPort,
    PackageDiscoveryPort,
)
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
    UnchangedContent,
)
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION, EducationalContent
from app.modules.evaluand_registry.domain.generator import resolve_declared_generator_version


class DeclaredGeneratorConflict(Exception):
    """The package's self-declared generator does not match the one this registration
    declared (ADR-0024's channel, cross-checked against ADR-0027's declared surface).

    Refused outright, with no override: the two declarations disagree about a plain fact, and
    the fix is to correct one of them — the same shape as a content-hash conflict (ADR-0027
    §4), which also has no override. `selected_id` of `None` (an `unknown` registration) never
    raises this: `unknown` is legitimate even when the package declares a generator (ADR-0024
    cl. 1), so that case is a caller-side notice, not a refusal.
    """

    def __init__(
        self,
        *,
        declared_name: str,
        declared_version: str,
        resolved_id: UUID | None,
        selected_id: UUID | None,
    ) -> None:
        self.declared_name = declared_name
        self.declared_version = declared_version
        self.resolved_id = resolved_id
        self.selected_id = selected_id
        super().__init__(
            f"the package declares '{declared_name} {declared_version}', "
            "which does not match the generator version this registration declared"
        )


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
    def __init__(
        self,
        discovery: PackageDiscoveryPort,
        register: RegisterContentVersion,
        generators: GeneratorRepositoryPort,
        generator_versions: GeneratorVersionRepositoryPort,
    ) -> None:
        self._discovery = discovery
        self._register = register
        self._generators = generators
        self._generator_versions = generator_versions

    def __call__(self, command: RegisterPackageFromSourceCommand) -> PackageRegistration:
        discovered = self._discovery.discover(command.package_format, command.source_locator)

        if discovered.declared_generator_name and discovered.declared_generator_version:
            resolved = resolve_declared_generator_version(
                discovered.declared_generator_name,
                discovered.declared_generator_version,
                self._generators.list_all(),
                self._generator_versions.list_all(),
            )
            resolved_id = resolved.id if resolved is not None else None
            selected_id = command.generator_version_id
            # `unknown` (selected_id is None) never conflicts (ADR-0024 cl. 1) — see the
            # exception's docstring.
            if selected_id is not None and selected_id != resolved_id:
                raise DeclaredGeneratorConflict(
                    declared_name=discovered.declared_generator_name,
                    declared_version=discovered.declared_generator_version,
                    resolved_id=resolved_id,
                    selected_id=selected_id,
                )

        # A declaration beats what discovery inferred; neither is required (ADR-0028).
        consumable_url = command.consumable_url or discovered.consumable_url

        try:
            content = self._register(
                RegisterContentVersionCommand(
                    package_format=discovered.package_format,
                    external_id=discovered.external_id,
                    # Straight from discovery, like the hash: not something a caller may
                    # override, because the package is the author of its own name (ADR-0059).
                    title=discovered.title,
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
