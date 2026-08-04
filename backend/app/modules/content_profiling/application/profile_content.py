"""Use case: profile one content version (13-code-qa §3.4).

Works with or without an `ExtractionAccepted` act — the manual path is exactly how the
samples that earn the acceptance are produced. Extraction breakage becomes a `failed`
profile + `ContentProfilingFailed`, never a crash; an existing `ok` profile for the same
coordinates is final (immutable — re-extracting is a new adapter version), while a
`failed` one is replaced in place, an exception only this manual path takes: the policy
never re-profiles existing coordinates, so replaying `ContentVersionRegistered` cannot
re-emit anything (ADR-0003).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from app.modules.content_profiling.application.ports import (
    ContentGatewayPort,
    DataRequirementNamespacePort,
    ExtractionAdapterPort,
    PackageFetcherPort,
    ProfileRepositoryPort,
)
from app.modules.content_profiling.domain import events
from app.modules.content_profiling.domain.profile import ContentProfile, ExtractionError
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class ContentNotFound(Exception):
    """The content id is not registered."""


class NoAdapterForFormat(Exception):
    """No extraction adapter exists for the content's package format."""


class ProfileAlreadyExists(Exception):
    """An `ok` profile already exists for (content, adapter version) — it is immutable."""


@dataclass(frozen=True)
class ProfileContentCommand:
    content_id: UUID


class ProfileContent:
    def __init__(
        self,
        profiles: ProfileRepositoryPort,
        contents: ContentGatewayPort,
        namespace: DataRequirementNamespacePort,
        adapters: Mapping[str, ExtractionAdapterPort],
        fetcher: PackageFetcherPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._profiles = profiles
        self._contents = contents
        self._namespace = namespace
        self._adapters = adapters
        self._fetcher = fetcher
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: ProfileContentCommand) -> ContentProfile:
        package = self._contents.get_package(command.content_id)
        if package is None:
            raise ContentNotFound(f"content {command.content_id} is not registered")
        adapter = self._adapters.get(package.package_format)
        if adapter is None:
            raise NoAdapterForFormat(
                f"no extraction adapter for package format '{package.package_format}'"
            )

        existing = self._profiles.get_status(command.content_id, adapter.adapter_version)
        if existing == "ok":
            raise ProfileAlreadyExists(
                f"content {command.content_id} already has an ok profile for adapter "
                f"version {adapter.adapter_version} — profiles are immutable; a different "
                "extraction is a new adapter version"
            )
        if existing == "failed":
            # Same transaction as the re-insert: no window without a row.
            self._profiles.delete_failed(command.content_id, adapter.adapter_version)

        try:
            entries, extras = adapter.extract(package, self._fetcher)
            profile = ContentProfile.ok(
                id=new_id(),
                content_id=command.content_id,
                package_format=package.package_format,
                adapter_version=adapter.adapter_version,
                capabilities=adapter.capabilities,
                canonical_ids=self._namespace.canonical_ids(),
                entries=entries,
                extras=extras,
            )
        except ExtractionError as exc:
            profile = ContentProfile.failed(
                id=new_id(),
                content_id=command.content_id,
                package_format=package.package_format,
                adapter_version=adapter.adapter_version,
                error=str(exc),
            )

        if not self._profiles.insert(profile):
            # A concurrent write got there first; nothing recorded, nothing emitted.
            raise ProfileAlreadyExists(
                f"content {command.content_id} was profiled concurrently for adapter "
                f"version {adapter.adapter_version}"
            )
        # Profile + event in the same transaction (ADR-0003).
        if profile.status == "ok":
            self._publisher.publish(events.content_profiled(profile))
        else:
            self._publisher.publish(events.content_profiling_failed(profile))
        self._uow.commit()
        return profile
