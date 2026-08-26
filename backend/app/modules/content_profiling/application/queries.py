"""Read-only queries of Content Profiling (13-code-qa §3.4: getProfile, getCapabilities)."""

from collections.abc import Collection, Mapping
from typing import Any
from uuid import UUID

from app.modules.content_profiling.application.dtos import (
    CapabilitiesSnapshot,
    ContentProfileSnapshot,
    ProfileEntrySnapshot,
    ProfileExtraSnapshot,
)
from app.modules.content_profiling.application.ports import (
    AcceptanceRepositoryPort,
    ExtractionAdapterPort,
    ProfileRepositoryPort,
)
from app.modules.content_profiling.domain.profile import ContentProfile


def _snapshot(profile: ContentProfile) -> ContentProfileSnapshot:
    return ContentProfileSnapshot(
        profile_id=profile.id,
        content_id=profile.content_id,
        package_format=profile.package_format,
        adapter_version=profile.adapter_version,
        status=profile.status,
        error=profile.error,
        profiled_at=profile.profiled_at,
        entries=tuple(
            ProfileEntrySnapshot(
                data_requirement_id=entry.data_requirement_id,
                provenance=entry.provenance,
                value=entry.value,
                quote=entry.quote,
                locator=entry.locator,
            )
            for entry in profile.entries
        ),
        extras=tuple(
            ProfileExtraSnapshot(
                name=extra.name, value=extra.value, quote=extra.quote, locator=extra.locator
            )
            for extra in profile.extras
        ),
    )


def get_profile(
    profiles: ProfileRepositoryPort, content_id: UUID, adapter_version: str | None = None
) -> ContentProfileSnapshot | None:
    """Without a version: the most recent ok profile, else the most recent at all."""
    profile = profiles.get(content_id, adapter_version)
    return _snapshot(profile) if profile is not None else None


def get_declared_data(profiles: ProfileRepositoryPort, content_id: UUID) -> dict[str, str]:
    """`{data_requirement_id: provenance}` over the content's most recent **ok** profile.

    Empty when there is no ok profile — which is not the same statement as an empty profile,
    and consumers are told to read it as "nothing is settled" rather than "nothing was
    declared" (ADR-0053 §2). The `status` guard lives here rather than in each caller because
    `get_profile` deliberately falls back to the most recent *failed* profile so the
    workbench can show what broke, and a consumer that forgot the guard would read a broken
    extraction as a statement about the course.

    The two cases a caller needs are both readable from the result: an id missing from the
    mapping is one no adapter declared, and an id mapped to `absent` is one the adapter
    looked for and did not find.
    """
    profile = profiles.get(content_id, None)
    if profile is None or profile.status != "ok":
        return {}
    return {entry.data_requirement_id: entry.provenance for entry in profile.entries}


def get_declared_values(
    profiles: ProfileRepositoryPort, content_id: UUID, requirement_ids: Collection[str]
) -> dict[str, Any]:
    """The declared values of the ids asked for, over the same profile `get_declared_data`
    reads — so the two can never disagree about which profile is in play (ADR-0057).

    Only what a person can read: a string or a list of strings. Anything else is omitted
    rather than handed on for a screen to guess at (ADR-0057 §4). An `absent` entry yields
    nothing either, which is the same statement its provenance already makes.

    The ids are a parameter and not a filter applied afterwards, because `lesson_bodies`
    carries the whole course text and has no business crossing this boundary to be dropped.
    """
    profile = profiles.get(content_id, None)
    if profile is None or profile.status != "ok":
        return {}
    wanted = set(requirement_ids)
    return {
        entry.data_requirement_id: entry.value
        for entry in profile.entries
        if entry.data_requirement_id in wanted
        and entry.provenance != "absent"
        and _is_readable(entry.value)
    }


def _is_readable(value: Any) -> bool:
    """A shape a rater can be shown as prose: one statement, or a list of them."""
    if isinstance(value, str):
        return True
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def list_profiles(profiles: ProfileRepositoryPort) -> list[ContentProfileSnapshot]:
    return [_snapshot(profile) for profile in profiles.list_all()]


def get_capabilities(
    adapters: Mapping[str, ExtractionAdapterPort],
    acceptances: AcceptanceRepositoryPort,
    package_format: str,
) -> CapabilitiesSnapshot | None:
    """Supply (adapter in code) × qualification (acceptance in the store)."""
    adapter = adapters.get(package_format)
    if adapter is None:
        return None
    return CapabilitiesSnapshot(
        package_format=adapter.package_format,
        adapter_version=adapter.adapter_version,
        capabilities=tuple(sorted(adapter.capabilities)),
        accepted=acceptances.is_accepted(adapter.package_format, adapter.adapter_version),
    )


def list_capabilities(
    adapters: Mapping[str, ExtractionAdapterPort], acceptances: AcceptanceRepositoryPort
) -> list[CapabilitiesSnapshot]:
    snapshots = [
        get_capabilities(adapters, acceptances, package_format)
        for package_format in sorted(adapters)
    ]
    return [snapshot for snapshot in snapshots if snapshot is not None]
