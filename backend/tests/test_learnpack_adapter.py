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
from app.shared.domain.value_domain import check_value, validate_spec
from tests.conftest import declared_value_domains

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"

NO_ACTIVITIES = {
    "multipleChoice": 0,
    "openQuestion": 0,
    "selectTheBlank": 0,
    "ordering": 0,
    "fillInTheBlank": 0,
}


def fixture_package(course: str) -> PackageDTO:
    """Artifacts as the registry would hold them, locators relative to the fixtures dir."""
    artifacts = []
    if (FIXTURES / course / "learn.json").exists():
        artifacts.append(ArtifactDTO(kind="manifest", locator=f"{course}/learn.json"))
    if (FIXTURES / course / ".learn" / "package-manifest.json").exists():
        artifacts.append(
            ArtifactDTO(kind="package_manifest", locator=f"{course}/.learn/package-manifest.json")
        )
    for path in sorted((FIXTURES / course).glob("exercises/*/*")):
        locator = path.relative_to(FIXTURES).as_posix()
        kind = "lesson_content" if path.name == "README.md" else "lesson_file"
        artifacts.append(ArtifactDTO(kind=kind, locator=locator))
    return PackageDTO(
        content_id=new_id(),
        package_format="LearnpackV1",
        consumable_url=f"https://{course}.learn-pack.com/",
        artifacts=tuple(artifacts),
    )


@pytest.fixture
def adapter() -> LearnpackV1Adapter:
    return LearnpackV1Adapter()


@pytest.fixture
def fetcher() -> FilesystemPackageFetcher:
    return FilesystemPackageFetcher(FIXTURES)


def by_id(entries):
    return {e.data_requirement_id: e for e in entries}


def by_slug(activities_entry):
    return {item["lessonSlug"]: item for item in activities_entry.value}


def test_adapter_is_registered_for_its_format():
    assert ADAPTERS_BY_FORMAT["LearnpackV1"].adapter_version == ADAPTER_VERSION
    assert ADAPTERS_BY_FORMAT["LearnpackV1"].capabilities == CAPABILITIES


def test_full_package_yields_cited_entries(adapter, fetcher):
    package = fixture_package("object-representation-in-python")
    entries, extras = adapter.extract(package, fetcher)

    # One entry per declared capability — and nothing else: objectives/audience/
    # prerequisites have no source in this format (ADR-0017), so no entry exists and
    # criteria requiring them derive not_applicable, not absent.
    assert {e.data_requirement_id for e in entries} == set(CAPABILITIES)
    entry = by_id(entries)

    inventory = entry["lesson_inventory"]
    assert inventory.provenance == "declared_structured"
    assert len(inventory.value) == 11
    # No description on purpose: the manifest's descriptions are LLM-generated summaries
    # projected from the syllabus — not the generator's declaration (ADR-0009).
    assert inventory.value[0] == {
        "lessonId": "00.0",
        "slug": "00.0-from-concept-to-code",
        "position": 0,
        "type": "READ",
        "title": "From Concept to Code",
    }
    assert inventory.locator["path"] == "$.lessons"

    assert {x.name for x in extras} == {"difficulty", "technologies"}


def test_lesson_bodies_carry_the_content_verbatim(adapter, fetcher):
    package = fixture_package("object-representation-in-python")
    entries, _ = adapter.extract(package, fetcher)
    bodies = by_id(entries)["lesson_bodies"]

    assert bodies.provenance == "declared_in_content"  # the content citing itself
    assert len(bodies.value) == 11
    by_lesson = {item["lessonSlug"]: item for item in bodies.value}
    writing = by_lesson["01.0-writing-python-classes"]
    assert writing["lessonId"] == "01.0"
    assert writing["body"].lstrip().startswith("# 01.0 Writing Python Classes")
    assert "readingTime" not in writing["body"]  # frontmatter stripped
    assert "class Warrior:" in writing["body"]  # the actual lesson text, verbatim


def test_lesson_activities_observed_from_the_real_course(adapter, fetcher):
    package = fixture_package("object-representation-in-python")
    entries, _ = adapter.extract(package, fetcher)
    lessons = by_slug(by_id(entries)["lesson_activities"])

    assert len(lessons) == 11
    quiz = lessons["03.0-what-you-know-now"]
    assert quiz["lessonId"] == "03.0"
    assert quiz["activities"]["multipleChoice"] == 8

    outro = lessons["04.0-course-outro"]
    assert outro["activities"]["openQuestion"] == 1

    coding = lessons["01.0-writing-python-classes"]
    # The internal app.solution.hide.py companion is authoring detail, not an exercise.
    assert coding["codeExercises"] == ["app.py"]

    exposition = lessons["01.1-attributes-and-values"]
    assert exposition["activities"] == NO_ACTIVITIES
    assert exposition["codeExercises"] == []


def test_the_other_real_course_keeps_its_numbering_drift_verbatim(adapter, fetcher):
    """Lessons '05' and '06' lack the NN.M form — real generator drift. Extraction
    records it verbatim; judging it is the well-formedness criterion's job, not ours."""
    package = fixture_package("introduction-to-generative-ai")
    entries, _ = adapter.extract(package, fetcher)
    inventory = by_id(entries)["lesson_inventory"]
    assert len(inventory.value) == 17
    assert [lesson["lessonId"] for lesson in inventory.value][-5:] == [
        "05",
        "05.1",
        "05.2",
        "05.3",
        "06",
    ]
    lessons = by_slug(by_id(entries)["lesson_activities"])
    assert lessons["01.0-what-is-generative-ai-really"]["activities"]["multipleChoice"] == 3
    assert lessons["03.1-from-prompt-to-tokens"]["activities"]["openQuestion"] == 1


def test_package_without_artifacts_yields_absent_lesson_data(adapter, fetcher):
    # A package with no artifacts reads as "looked, nothing there" → absent. If
    # LearnpackV1 ever guarantees artifacts at registration, revisit: the honest
    # reading would then be a failed profile.
    package = PackageDTO(
        content_id=new_id(),
        package_format="LearnpackV1",
        consumable_url="https://no-artifacts.learn-pack.com/",
    )
    entries, extras = adapter.extract(package, fetcher)
    assert by_id(entries)["lesson_inventory"].provenance == "absent"
    assert by_id(entries)["lesson_bodies"].provenance == "absent"
    assert by_id(entries)["lesson_activities"].provenance == "absent"
    assert extras == ()


def test_every_component_type_is_counted_and_decoys_are_not(adapter, fetcher):
    package = fixture_package("bare-course")
    entries, _ = adapter.extract(package, fetcher)
    lessons = by_slug(by_id(entries)["lesson_activities"])

    sampler = lessons["01-activity-sampler"]
    # One of each; the checkbox inside a foreign fence and the author-facing
    # code_challenge_proposal block must NOT count.
    assert sampler["activities"] == {
        "multipleChoice": 1,
        "openQuestion": 1,
        "selectTheBlank": 1,
        "ordering": 1,
        "fillInTheBlank": 1,
    }

    assert lessons["00-frontmatter-only"]["activities"] == NO_ACTIVITIES
    # A lesson with no README still reports its exercise files.
    no_readme = lessons["01-no-readme"]
    assert no_readme["lessonId"] == "01.0"
    assert no_readme["codeExercises"] == ["app.py"]


def test_lessons_with_spanish_only_declarations_fall_back_verbatim(adapter, fetcher):
    package = fixture_package("bare-course")
    entries, _ = adapter.extract(package, fetcher)
    inventory = by_id(entries)["lesson_inventory"]
    no_readme = next(lesson for lesson in inventory.value if lesson["lessonId"] == "01.0")
    assert no_readme["title"] == "Sin README"  # declared es-only; never composed


def test_malformed_manifest_fails_extraction_instead_of_half_profiling(adapter, fetcher):
    package = fixture_package("broken-course")
    with pytest.raises(ExtractionError, match="JSON"):
        adapter.extract(package, fetcher)


def test_extraction_is_deterministic(adapter, fetcher):
    package = fixture_package("object-representation-in-python")
    assert adapter.extract(package, fetcher) == adapter.extract(package, fetcher)


def test_extraction_satisfies_the_profile_aggregate(adapter, fetcher):
    """The adapter's output builds a valid ok profile — the two halves fit."""
    package = fixture_package("object-representation-in-python")
    entries, extras = adapter.extract(package, fetcher)
    profile = ContentProfile.ok(
        id=new_id(),
        content_id=package.content_id,
        package_format="LearnpackV1",
        adapter_version=ADAPTER_VERSION,
        capabilities=CAPABILITIES,
        value_domains=declared_value_domains(),
        entries=entries,
        extras=extras,
    )
    assert profile.status == "ok"


@pytest.mark.parametrize(
    "course",
    ["object-representation-in-python", "introduction-to-generative-ai", "bare-course"],
)
def test_every_extracted_value_matches_the_declared_value_domain(adapter, fetcher, course):
    """Supply meets demand on SHAPE, over real packages (ADR-0020).

    The shapes come from the instrument the team authors, so this is the test that keeps
    the value domains honest: change what the adapter emits without changing the
    declaration (or the reverse) and it fails here, not in an assessor months later.
    """
    domains = declared_value_domains()
    entries, _ = adapter.extract(fixture_package(course), fetcher)

    problems = [
        problem
        for e in entries
        if e.provenance != "absent"
        for problem in check_value(e.value, domains[e.data_requirement_id], e.data_requirement_id)
    ]
    assert problems == []


def test_the_declared_value_domains_are_well_formed():
    """Every capability the adapter claims has a usable declaration behind it."""
    domains = declared_value_domains()
    assert CAPABILITIES <= set(domains)
    assert [p for d in domains.values() for p in validate_spec(d)] == []
