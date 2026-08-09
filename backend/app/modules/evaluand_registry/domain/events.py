"""Domain events published by the Evaluand Registry (design 10 §events)."""

from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.generator import GeneratorArtifact, GeneratorVersion
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "EducationalContent"
GENERATOR_AGGREGATE = "GeneratorVersion"
BRIEF_AGGREGATE = "GenerationBrief"


def generator_version_registered(generator: GeneratorVersion) -> DomainEvent:
    return DomainEvent(
        event_type="GeneratorVersionRegistered",
        aggregate_type=GENERATOR_AGGREGATE,
        aggregate_id=str(generator.id),
        payload={
            "generatorVersionId": str(generator.id),
            "name": generator.name,
            "version": generator.version,
        },
    )


def brief_registered(brief: GenerationBrief) -> DomainEvent:
    return DomainEvent(
        event_type="BriefRegistered",
        aggregate_type=BRIEF_AGGREGATE,
        aggregate_id=str(brief.id),
        payload={
            "briefId": str(brief.id),
            "fieldKeys": sorted(brief.fields),
            # Null for manually registered briefs (ADR-0022).
            "briefHash": brief.brief_hash,
        },
    )


def generator_artifact_registered(artifact: GeneratorArtifact) -> DomainEvent:
    return DomainEvent(
        event_type="GeneratorArtifactRegistered",
        aggregate_type=GENERATOR_AGGREGATE,
        aggregate_id=str(artifact.generator_version_id),
        payload={
            "artifactId": str(artifact.id),
            "generatorVersionId": str(artifact.generator_version_id),
            "kind": artifact.kind,
            "locator": artifact.locator,
        },
    )


def generator_attributed(content: EducationalContent) -> DomainEvent:
    """A generator discovered after registration (ADR-0024) — same aggregate as the
    registration, so the outbox and its cleanup already carry it."""
    return DomainEvent(
        event_type="GeneratorAttributed",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(content.id),
        payload={
            "contentId": str(content.id),
            "generatorVersionId": str(content.generator_version_id),
            "attributedBy": str(content.generator_attributed_by),
        },
    )


def content_version_registered(content: EducationalContent) -> DomainEvent:
    return DomainEvent(
        event_type="ContentVersionRegistered",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(content.id),
        payload={
            "contentId": str(content.id),
            "packageFormat": content.package_format,
            "externalId": content.external_id,
            "version": content.version,
            # Null when no deployed, human-consumable instance is declared (ADR-0028).
            "consumableUrl": content.consumable_url,
            # Nullable on purpose: absent brief = recorded absent; null generator = unknown.
            "briefId": str(content.brief_id) if content.brief_id else None,
            "generatorVersionId": (
                str(content.generator_version_id) if content.generator_version_id else None
            ),
            "editProvenance": content.edit_provenance,
            # Artifacts stay out of the payload — consumers read them via getContentPackage.
        },
    )
