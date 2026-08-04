"""LearnpackV1 extraction against frozen real packages — the investment of Content
Profiling (design 10: fixtures, not model). No DB, no network."""

from pathlib import Path

import pytest

from app.modules.content_profiling.application.dtos import ArtifactDTO, PackageDTO
from app.modules.content_profiling.domain.profile import ContentProfile, ExtractionError
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.adapters.learnpack_v1 import (
    ADAPTER_VERSION,
    CAPABILITIES,
    LearnpackV1Adapter,
)
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.shared.domain.ids import new_id

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"

DECLARED_METADATA = {
    "learningObjectives": [
        "Define Python classes with __init__, attributes, and methods",
        "Create and use object instances with dot notation",
    ],
    "targetAudience": "Beginner developers who understand OOP concepts",
    "prerequisites": ["Basic Python", "Object-oriented programming concepts"],
}


def fixture_package(course: str, metadata: dict | None = None) -> PackageDTO:
    """Artifacts as the registry would hold them, locators relative to the fixtures dir."""
    artifacts = []
    if (FIXTURES / course / "learn.json").exists():
        artifacts.append(ArtifactDTO(kind="manifest", locator=f"{course}/learn.json"))
    if (FIXTURES / course / ".learn" / "config.json").exists():
        artifacts.append(
            ArtifactDTO(kind="exercise_config", locator=f"{course}/.learn/config.json")
        )
    for readme in sorted((FIXTURES / course).glob("exercises/*/README.md")):
        locator = readme.relative_to(FIXTURES).as_posix()
        artifacts.append(ArtifactDTO(kind="exercise_instructions", locator=locator))
    return PackageDTO(
        content_id=new_id(),
        package_format="LearnpackV1",
        consumable_url=f"https://{course}.learn-pack.com/",
        artifacts=tuple(artifacts),
        declared_metadata=metadata if metadata is not None else {},
    )


@pytest.fixture
def adapter() -> LearnpackV1Adapter:
    return LearnpackV1Adapter()


@pytest.fixture
def fetcher() -> FilesystemPackageFetcher:
    return FilesystemPackageFetcher(FIXTURES)


def by_id(entries):
    return {e.data_requirement_id: e for e in entries}


def test_adapter_is_registered_for_its_format():
    assert ADAPTERS_BY_FORMAT["LearnpackV1"].adapter_version == ADAPTER_VERSION


def test_full_package_with_declared_metadata_yields_cited_entries(adapter, fetcher):
    package = fixture_package("object-representation-in-python", DECLARED_METADATA)
    entries, extras = adapter.extract(package, fetcher)

    assert {e.data_requirement_id for e in entries} == set(CAPABILITIES)
    entry = by_id(entries)

    objectives = entry["learning_objectives"]
    assert objectives.provenance == "declared_structured"
    assert objectives.value == DECLARED_METADATA["learningObjectives"]
    assert "dot notation" in objectives.quote  # verbatim citation (ADR-0009)
    assert objectives.locator == {"source": "metadata", "key": "learningObjectives"}

    audience = entry["target_audience"]
    assert audience.provenance == "declared_structured"
    assert audience.value == "Beginner developers who understand OOP concepts"

    exercises = entry["practice_exercises"]
    assert exercises.provenance == "declared_structured"
    assert len(exercises.value) == 11
    assert all(item["hasInstructions"] for item in exercises.value)
    assert {"exerciseId": "01.0-writing-python-classes", "hasInstructions": True} in (
        exercises.value
    )
    assert "01.0-writing-python-classes" in exercises.quote
    assert exercises.locator["kind"] == "exercise_config"

    assert {x.name for x in extras} == {"difficulty", "technologies"}
    assert by_id_extra(extras)["difficulty"].value == "beginner"


def by_id_extra(extras):
    return {x.name: x for x in extras}


def test_the_other_real_course_extracts_its_full_exercise_index(adapter, fetcher):
    package = fixture_package("introduction-to-generative-ai", DECLARED_METADATA)
    entries, _ = adapter.extract(package, fetcher)
    exercises = by_id(entries)["practice_exercises"]
    assert len(exercises.value) == 17
    assert all(item["hasInstructions"] for item in exercises.value)


def test_capability_without_data_yields_explicit_absent_not_missing_entry(adapter, fetcher):
    package = fixture_package("object-representation-in-python", metadata=None)
    entries, _ = adapter.extract(package, fetcher)
    entry = by_id(entries)
    for requirement_id in ("learning_objectives", "target_audience", "prerequisites"):
        assert entry[requirement_id].provenance == "absent"
        assert entry[requirement_id].value is None
        assert entry[requirement_id].quote is None
    # The package itself still yields its exercises.
    assert entry["practice_exercises"].provenance == "declared_structured"


def test_package_without_artifacts_yields_absent_exercises(adapter, fetcher):
    # Decision fixed here (13-code §3.4): a package with no artifacts reads as "looked,
    # nothing there" → absent. If LearnpackV1 ever guarantees artifacts at registration,
    # revisit: the honest reading would then be a failed profile.
    package = PackageDTO(
        content_id=new_id(),
        package_format="LearnpackV1",
        consumable_url="https://no-artifacts.learn-pack.com/",
    )
    entries, extras = adapter.extract(package, fetcher)
    assert by_id(entries)["practice_exercises"].provenance == "absent"
    assert extras == ()


def test_exercises_without_learner_facing_instructions_are_observed(adapter, fetcher):
    package = fixture_package("bare-course")
    entries, _ = adapter.extract(package, fetcher)
    exercises = by_id(entries)["practice_exercises"]
    assert exercises.value == [
        {"exerciseId": "00-frontmatter-only", "hasInstructions": False},
        {"exerciseId": "01-no-readme", "hasInstructions": False},
    ]


def test_malformed_config_fails_extraction_instead_of_half_profiling(adapter, fetcher):
    package = fixture_package("broken-course")
    with pytest.raises(ExtractionError, match="JSON"):
        adapter.extract(package, fetcher)


def test_extraction_is_deterministic(adapter, fetcher):
    package = fixture_package("object-representation-in-python", DECLARED_METADATA)
    assert adapter.extract(package, fetcher) == adapter.extract(package, fetcher)


def test_extraction_satisfies_the_profile_aggregate(adapter, fetcher):
    """The adapter's output builds a valid ok profile — the two halves fit."""
    package = fixture_package("object-representation-in-python", DECLARED_METADATA)
    entries, extras = adapter.extract(package, fetcher)
    profile = ContentProfile.ok(
        id=new_id(),
        content_id=package.content_id,
        package_format="LearnpackV1",
        adapter_version=ADAPTER_VERSION,
        capabilities=CAPABILITIES,
        canonical_ids=CAPABILITIES,
        entries=entries,
        extras=extras,
    )
    assert profile.status == "ok"
