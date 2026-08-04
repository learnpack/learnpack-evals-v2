"""Domain events published by Content Profiling (design 09 §events).

Payloads carry coordinates only — no entries: consumers read the profile through the
public query (`get_profile`), the same convention `ContentVersionRegistered` follows
with package artifacts.
"""

from uuid import UUID

from app.modules.content_profiling.domain.profile import ContentProfile
from app.shared.domain.events import DomainEvent

PROFILE_AGGREGATE_TYPE = "ContentProfile"
ACCEPTANCE_AGGREGATE_TYPE = "ExtractionAcceptance"


def content_profiled(profile: ContentProfile) -> DomainEvent:
    return DomainEvent(
        event_type="ContentProfiled",
        aggregate_type=PROFILE_AGGREGATE_TYPE,
        aggregate_id=str(profile.id),
        payload={
            "profileId": str(profile.id),
            "contentId": str(profile.content_id),
            "packageFormat": profile.package_format,
            "adapterVersion": profile.adapter_version,
        },
    )


def content_profiling_failed(profile: ContentProfile) -> DomainEvent:
    return DomainEvent(
        event_type="ContentProfilingFailed",
        aggregate_type=PROFILE_AGGREGATE_TYPE,
        aggregate_id=str(profile.id),
        payload={
            "profileId": str(profile.id),
            "contentId": str(profile.content_id),
            "packageFormat": profile.package_format,
            "adapterVersion": profile.adapter_version,
            "error": profile.error,
        },
    )


def extraction_accepted(
    package_format: str, adapter_version: str, accepted_by: UUID
) -> DomainEvent:
    return DomainEvent(
        event_type="ExtractionAccepted",
        aggregate_type=ACCEPTANCE_AGGREGATE_TYPE,
        aggregate_id=f"{package_format}:{adapter_version}",
        payload={
            "packageFormat": package_format,
            "adapterVersion": adapter_version,
            "acceptedBy": str(accepted_by),
        },
    )
