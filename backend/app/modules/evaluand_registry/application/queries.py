"""Read-only query port of the Evaluand Registry (11-connect §published language).

`getContentSnapshot` is how Evaluation and Orchestration read content — never by joining
against `contents` themselves (08-code.md §3, FK rule).
"""

from uuid import UUID

from app.modules.evaluand_registry.application.dtos import (
    BriefDTO,
    ContentPackageDTO,
    ContentSnapshot,
    GeneratorDTO,
    GeneratorVersionDTO,
    PackageArtifactDTO,
)
from app.modules.evaluand_registry.application.ports import (
    BriefRepositoryPort,
    ContentRepositoryPort,
    GeneratorRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.generator import Generator, GeneratorVersion


def _to_snapshot(content: EducationalContent) -> ContentSnapshot:
    return ContentSnapshot(
        content_id=content.id,
        package_format=content.package_format,
        external_id=content.external_id,
        version=content.version,
        consumable_url=content.consumable_url,
        brief_id=content.brief_id,
        generator_version_id=content.generator_version_id,
        edit_provenance=content.edit_provenance,
        generator_attributed_by=content.generator_attributed_by,
        generator_attributed_at=content.generator_attributed_at,
    )


def get_content_package(
    contents: ContentRepositoryPort, content_id: UUID
) -> ContentPackageDTO | None:
    """The complete work product — what the extraction adapter reads (design 11)."""
    content = contents.get_by_id(content_id)
    if content is None:
        return None
    return ContentPackageDTO(
        content_id=content.id,
        package_format=content.package_format,
        consumable_url=content.consumable_url,
        artifacts=[
            PackageArtifactDTO(kind=a.kind, locator=a.locator, format=a.format)
            for a in content.package.artifacts
        ],
    )


def get_content_snapshot(
    contents: ContentRepositoryPort, content_id: UUID
) -> ContentSnapshot | None:
    content = contents.get_by_id(content_id)
    if content is None:
        return None
    return _to_snapshot(content)


def list_content_snapshots(contents: ContentRepositoryPort) -> list[ContentSnapshot]:
    return [_to_snapshot(content) for content in contents.list_all()]


def get_available_contents(
    contents: ContentRepositoryPort,
    package_format: str | None = None,
    brief_ids: list[UUID] | None = None,
    generator_known: bool = False,
    generator_version_ids: list[UUID] | None = None,
) -> list[ContentSnapshot]:
    """What is registered, filtered for dataset composition (13-code §3.6):
    by commission (`brief_ids`), by format, by the versions a study's scope names
    (`generator_version_ids`, ADR-0044), or excluding unknown-generator contents."""
    return [
        _to_snapshot(content)
        for content in contents.list_filtered(
            package_format=package_format,
            brief_ids=brief_ids,
            generator_known=generator_known,
            generator_version_ids=generator_version_ids,
        )
    ]


def _to_generator_dto(generator: Generator) -> GeneratorDTO:
    return GeneratorDTO(generator_id=generator.id, name=generator.name)


def _to_generator_version_dto(version: GeneratorVersion, name: str) -> GeneratorVersionDTO:
    return GeneratorVersionDTO(
        generator_version_id=version.id,
        generator_id=version.generator_id,
        name=name,
        version=version.version,
        metadata=version.metadata,
    )


def _to_brief_dto(brief: GenerationBrief) -> BriefDTO:
    return BriefDTO(
        brief_id=brief.id,
        brief=brief.brief,
        fields=brief.fields,
        brief_hash=brief.brief_hash,
    )


def list_generators(generators: GeneratorRepositoryPort) -> list[GeneratorDTO]:
    return [_to_generator_dto(g) for g in generators.list_all()]


# The lineage name is joined in Python, not in SQL: the repositories in this module return
# domain objects without exception, and the lineage list is small and already fetched for other
# reasons. Two reads where there was one, bounded by that cardinality (ADR-0031, ADR-0006).
def get_generator_version(
    versions: GeneratorVersionRepositoryPort,
    generators: GeneratorRepositoryPort,
    generator_version_id: UUID,
) -> GeneratorVersionDTO | None:
    version = versions.get_by_id(generator_version_id)
    if version is None:
        return None
    generator = generators.get_by_id(version.generator_id)
    # The FK guarantees it; an orphan would be a corrupted store, not a missing DTO.
    assert generator is not None
    return _to_generator_version_dto(version, generator.name)


def list_generator_versions(
    versions: GeneratorVersionRepositoryPort,
    generators: GeneratorRepositoryPort,
) -> list[GeneratorVersionDTO]:
    names = {g.id: g.name for g in generators.list_all()}
    dtos = [_to_generator_version_dto(v, names[v.generator_id]) for v in versions.list_all()]
    # Stable sort over a list the repository already ordered by registration, so the result is
    # (lineage name, registration order) — versions of one generator arrive together, oldest
    # first, which is what a grouped reader wants and what a raw id ordering would scramble.
    dtos.sort(key=lambda dto: dto.name.lower())
    return dtos


def get_brief(briefs: BriefRepositoryPort, brief_id: UUID) -> BriefDTO | None:
    brief = briefs.get_by_id(brief_id)
    return None if brief is None else _to_brief_dto(brief)


def list_briefs(briefs: BriefRepositoryPort) -> list[BriefDTO]:
    return [_to_brief_dto(b) for b in briefs.list_all()]
