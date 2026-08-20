"""Use case: profile one content version (13-code-qa §3.4).

Works with or without an `ExtractionAccepted` act — the manual path is exactly how the
samples that earn the acceptance are produced. Extraction breakage becomes a `failed`
profile + `ContentProfilingFailed`, never a crash; an existing `ok` profile for the same
coordinates is final (immutable — re-extracting is a new adapter version), while a
`failed` one is replaced in place, an exception only this manual path takes: the policy
never re-profiles existing coordinates, so replaying `ContentVersionRegistered` cannot
re-emit anything (ADR-0003).
"""

from collections.abc import Mapping, Sequence
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


class _ReadOnce:
    """A fetcher that answers a locator it has already answered from memory.

    An adapter's entry builders are deliberately independent: each reads and cites the
    artifact it cites, without asking what another one read. That is why V2 downloaded
    `lesson_plan.json` three times — the design was right and the bill was not. Rather than
    couple the builders to each other, the fetcher stops the repetition.

    It wraps the injected fetcher for the length of ONE extraction, which is the only window
    in which "the same artifact" is a safe thing to say: a package's bytes are what they were
    when discovery hashed them, and the next extraction gets a new instance. Scoped by
    construction, so there is no composition root to remember and no caller that can share it
    by accident.
    """

    def __init__(self, fetcher: PackageFetcherPort) -> None:
        self._fetcher = fetcher
        self._read: dict[str, bytes] = {}

    def fetch(self, locator: str) -> bytes:
        if locator not in self._read:
            self._read[locator] = self._fetcher.fetch(locator)
        return self._read[locator]

    def fetch_all(self, locators: Sequence[str]) -> Mapping[str, bytes]:
        """Only what is not in hand goes to the wrapped fetcher — as one group, so a wave
        that is half remembered does not become a walk over the rest."""
        missing = [locator for locator in locators if locator not in self._read]
        if missing:
            self._read.update(self._fetcher.fetch_all(missing))
        return {locator: self._read[locator] for locator in locators}


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
            entries, extras = adapter.extract(package, _ReadOnce(self._fetcher))
            profile = ContentProfile.ok(
                id=new_id(),
                content_id=command.content_id,
                package_format=package.package_format,
                adapter_version=adapter.adapter_version,
                capabilities=adapter.capabilities,
                value_domains=self._namespace.value_domains(),
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
