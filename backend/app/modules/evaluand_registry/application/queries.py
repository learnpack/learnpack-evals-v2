"""Read-only query port of the Evaluand Registry (11-connect §published language).

`getContentSnapshot` is how Evaluation and Orchestration read content — never by joining
against `contents` themselves (08-code.md §3, FK rule).
"""

from uuid import UUID

from app.modules.evaluand_registry.application.dtos import (
    BriefDTO,
    ContentPackageDTO,
    ContentSnapshot,
    GeneratorArtifactDTO,
    GeneratorVersionDTO,
    PackageArtifactDTO,
)
from app.modules.evaluand_registry.application.ports import (
    BriefRepositoryPort,
    ContentRepositoryPort,
    GeneratorArtifactRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.generator import GeneratorVersion


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
) -> list[ContentSnapshot]:
    """What is registered, filtered for dataset composition (13-code §3.6):
    by commission (`brief_ids`), by format, or excluding unknown-generator contents."""
    return [
        _to_snapshot(content)
        for content in contents.list_filtered(
            package_format=package_format,
            brief_ids=brief_ids,
            generator_known=generator_known,
        )
    ]


def _to_generator_dto(generator: GeneratorVersion) -> GeneratorVersionDTO:
    return GeneratorVersionDTO(
        generator_version_id=generator.id,
        name=generator.name,
        version=generator.version,
        metadata=generator.metadata,
    )


def _to_brief_dto(brief: GenerationBrief) -> BriefDTO:
    return BriefDTO(brief_id=brief.id, brief=brief.brief, fields=brief.fields)


def get_generator_version(
    generators: GeneratorVersionRepositoryPort, generator_version_id: UUID
) -> GeneratorVersionDTO | None:
    generator = generators.get_by_id(generator_version_id)
    return None if generator is None else _to_generator_dto(generator)


def list_generator_versions(
    generators: GeneratorVersionRepositoryPort,
) -> list[GeneratorVersionDTO]:
    return [_to_generator_dto(g) for g in generators.list_all()]


def get_brief(briefs: BriefRepositoryPort, brief_id: UUID) -> BriefDTO | None:
    brief = briefs.get_by_id(brief_id)
    return None if brief is None else _to_brief_dto(brief)


def list_briefs(briefs: BriefRepositoryPort) -> list[BriefDTO]:
    return [_to_brief_dto(b) for b in briefs.list_all()]


def list_generator_artifacts(
    artifacts: GeneratorArtifactRepositoryPort, generator_version_id: UUID
) -> list[GeneratorArtifactDTO]:
    return [
        GeneratorArtifactDTO(
            artifact_id=a.id,
            generator_version_id=a.generator_version_id,
            kind=a.kind,
            locator=a.locator,
            format=a.format,
        )
        for a in artifacts.list_for_generator(generator_version_id)
    ]
