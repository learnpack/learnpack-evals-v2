"""Domain events published by the Evaluand Registry (design 10 §events)."""

from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.generator import Generator, GeneratorVersion
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "EducationalContent"
GENERATOR_AGGREGATE = "Generator"
GENERATOR_VERSION_AGGREGATE = "GeneratorVersion"
BRIEF_AGGREGATE = "GenerationBrief"


def generator_registered(generator: Generator) -> DomainEvent:
    """A lineage was minted (ADR-0031) — the rare act, as opposed to registering a version
    under one."""
    return DomainEvent(
        event_type="GeneratorRegistered",
        aggregate_type=GENERATOR_AGGREGATE,
        aggregate_id=str(generator.id),
        payload={"generatorId": str(generator.id), "name": generator.name},
    )


def generator_version_registered(version: GeneratorVersion, generator: Generator) -> DomainEvent:
    """The lineage travels by id *and* by name. An event is a past fact in an append-only
    outbox, and a payload that needs a join against current state to be read is a worse
    record — so the name is carried redundantly, on purpose."""
    return DomainEvent(
        event_type="GeneratorVersionRegistered",
        aggregate_type=GENERATOR_VERSION_AGGREGATE,
        aggregate_id=str(version.id),
        payload={
            "generatorVersionId": str(version.id),
            "generatorId": str(generator.id),
            "name": generator.name,
            "version": version.version,
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


def consumable_url_declared(content: EducationalContent, previous: str | None) -> DomainEvent:
    """A deployment declared after registration (ADR-0054).

    `from` and `to`, because the audit question is never *what is this content's URL* — the
    row answers that — but *what changed, and who decided*. Only emitted when something did
    change; a no-op in the outbox is noise a future reader has to rule out.
    """
    return DomainEvent(
        event_type="ConsumableUrlDeclared",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(content.id),
        payload={
            "contentId": str(content.id),
            # Null means this content declared no deployment until now (ADR-0028).
            "from": previous,
            "to": content.consumable_url,
            "declaredBy": str(content.consumable_url_declared_by),
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
