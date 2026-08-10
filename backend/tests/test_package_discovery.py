"""Mechanical discovery of the declared surface (ADR-0027), against the frozen real
packages — the same investment the extraction suite rides on. No DB, no network."""

import json
import shutil
from pathlib import Path

import pytest

from app.modules.content_profiling.infrastructure.adapters import learnpack_v1 as extraction
from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
from app.modules.evaluand_registry.infrastructure import package_discovery
from app.modules.evaluand_registry.infrastructure.brief_intake import LearnpackV1BriefIntake
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    HttpPackageRoot,
    LearnpackV1Discovery,
)

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"


def discover(course: str, locator_base: str | None = None):
    return LearnpackV1Discovery().discover(
        FilesystemPackageRoot(FIXTURES / course, locator_base=locator_base)
    )


def kinds_and_locators(discovered):
    return {(a.kind, a.locator) for a in discovered.artifacts}


# ------------------------------------------------------------------ the declared surface


def glob_expectation(course: str) -> set[tuple[str, str]]:
    """What the seeder's hand-rolled artifact list produced before discovery took over —
    the equivalence proof for migrating it."""
    course_dir = FIXTURES / course
    expected = {
        ("manifest", f"{course}/learn.json"),
        ("package_manifest", f"{course}/.learn/package-manifest.json"),
    }
    if (course_dir / ".learn" / "initialSyllabus.json").exists():
        expected.add(("syllabus", f"{course}/.learn/initialSyllabus.json"))
    for path in course_dir.glob("exercises/*/*"):
        kind = "lesson_content" if path.name == "README.md" else "lesson_file"
        expected.add((kind, path.relative_to(FIXTURES).as_posix()))
    return expected


@pytest.mark.parametrize(
    "course",
    [
        "introduction-to-generative-ai",
        "object-representation-in-python",
        "ai-concepts-an-exploration-inside-ai",
        "html-fundamentals",
        "orchestrating-a-multi-agent-system-in-langgraph",
    ],
)
def test_discovery_enumerates_what_the_package_declares(course):
    """`.learn/config.json`'s enumeration (translations + files) covers exactly what
    walking the directory found — no walking needed, so the same code works over HTTP."""
    assert kinds_and_locators(discover(course, locator_base=course)) == glob_expectation(course)


def test_the_descriptor_comes_from_the_manifest():
    discovered = discover("object-representation-in-python")
    assert discovered.package_format == "LearnpackV1"
    assert discovered.external_id == "object-representation-in-python"
    assert discovered.title == "Object Representation in Python"


def test_a_missing_syllabus_is_omitted_not_fatal():
    """The one soft artifact: an absent commission is a recorded state (ADR-0022), not a
    broken package."""
    discovered = discover("bare-course")
    surface = kinds_and_locators(discovered)
    assert "syllabus" not in {kind for kind, _ in surface}
    # translations enumerate the lesson bodies; files[] the code — including an exercise
    # that has no README at all.
    assert ("lesson_content", "exercises/00-frontmatter-only/README.md") in surface
    assert ("lesson_file", "exercises/01-no-readme/app.py") in surface


# ------------------------------------------------------------------ hard failures


def test_a_package_without_its_manifest_fails():
    # broken-course has no learn.json: not discoverable, not registrable (ADR-0027).
    with pytest.raises(PackageDiscoveryError):
        discover("broken-course")


def test_a_package_without_the_exercise_enumeration_fails(tmp_path):
    shutil.copytree(FIXTURES / "bare-course", tmp_path / "course")
    (tmp_path / "course" / ".learn" / "config.json").unlink()

    with pytest.raises(PackageDiscoveryError):
        LearnpackV1Discovery().discover(FilesystemPackageRoot(tmp_path / "course"))


def test_a_manifest_without_a_slug_fails(tmp_path):
    shutil.copytree(FIXTURES / "bare-course", tmp_path / "course")
    (tmp_path / "course" / "learn.json").write_text(json.dumps({"title": "x"}), encoding="utf-8")

    with pytest.raises(PackageDiscoveryError):
        LearnpackV1Discovery().discover(FilesystemPackageRoot(tmp_path / "course"))


def test_a_config_declared_file_that_is_missing_fails(tmp_path):
    """A lying enumeration fails loudly at fetch/hash time — a partially discovered
    package would silently narrow the declared surface."""
    shutil.copytree(FIXTURES / "bare-course", tmp_path / "course")
    (tmp_path / "course" / "exercises" / "01-no-readme" / "app.py").unlink()

    with pytest.raises(PackageDiscoveryError):
        LearnpackV1Discovery().discover(FilesystemPackageRoot(tmp_path / "course"))


# The refusal of an unknown format and the content-hash contract (deterministic,
# root-independent, byte-sensitive) are pinned per format in tests/test_format_contract.py.


# ------------------------------------------------------------------ vocabulary + roots


def test_discovery_writes_the_kinds_the_extraction_adapter_reads():
    """Single-writer vocabulary (ADR-0027). Tests may look across the module seam to pin
    the alignment; app code must not."""
    assert package_discovery.KIND_MANIFEST == extraction.KIND_MANIFEST
    assert package_discovery.KIND_PACKAGE_MANIFEST == extraction.KIND_PACKAGE_MANIFEST
    assert package_discovery.KIND_LESSON_CONTENT == extraction.KIND_LESSON_CONTENT
    assert package_discovery.KIND_LESSON_FILE == extraction.KIND_LESSON_FILE


def test_the_brief_intake_finds_the_discovered_syllabus():
    discovered = discover("introduction-to-generative-ai", locator_base="intro")
    rows = [{"kind": a.kind, "locator": a.locator} for a in discovered.artifacts]
    assert LearnpackV1BriefIntake().locate(rows) == "intro/.learn/initialSyllabus.json"


def test_only_an_http_root_declares_a_consumable_url():
    """ADR-0028: the served root of a LearnPack package IS the running course, so an http
    root declares one. A filesystem root never does — the dev mount makes the locators
    fetchable, which is a transport arrangement, not a deployment."""
    assert HttpPackageRoot("https://x.learn-pack.com/").consumable_url == "https://x.learn-pack.com"
    assert (
        FilesystemPackageRoot(
            FIXTURES, locator_base="http://localhost:8000/packages/g/c"
        ).consumable_url
        is None
    )
    assert FilesystemPackageRoot(FIXTURES, locator_base="bare-course").consumable_url is None
    assert FilesystemPackageRoot(FIXTURES).consumable_url is None
    # The seam one level up — a filesystem DISCOVERY yielding no consumable URL — is
    # pinned per format in tests/test_format_contract.py (ADR-0028).
