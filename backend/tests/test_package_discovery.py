"""Mechanical discovery of the declared surface (ADR-0027), against the frozen real
packages — the same investment the extraction suite rides on. No DB, no network."""

import json
import shutil
import threading
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
from app.platform.concurrency import all_at_once

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


# ------------------------------------------------------- the leaves are read together


class WaveRecordingRoot:
    """A root that remembers each GROUP it was asked for, not only each path. Asserting that
    a discovery declared its independent reads as independent needs the shape of the asks,
    which a flat list of paths cannot show."""

    def __init__(self, course: str) -> None:
        self._inner = FilesystemPackageRoot(FIXTURES / course)
        self.waves: list[list[str]] = []
        self.one_by_one: list[str] = []

    def fetch(self, relative_path: str) -> bytes:
        self.one_by_one.append(relative_path)
        return self._inner.fetch(relative_path)

    def fetch_all(self, relative_paths):
        self.waves.append(list(relative_paths))
        return {path: self._inner.fetch(path) for path in relative_paths}

    def locator_for(self, relative_path: str) -> str:
        return self._inner.locator_for(relative_path)

    @property
    def consumable_url(self) -> str | None:
        return self._inner.consumable_url


def test_the_leaves_a_package_enumerates_are_asked_for_in_one_wave():
    """The manifests are read one at a time because each names the next; everything they
    enumerate is then asked for at once. This is all the discovery says — whether "at once"
    buys anything is the root's business, and the ceiling on it is the transport's."""
    root = WaveRecordingRoot("object-representation-in-python")
    discovered = LearnpackV1Discovery().discover(root)

    leaves = [
        a.locator
        for a in discovered.artifacts
        if a.kind in (package_discovery.KIND_LESSON_CONTENT, package_discovery.KIND_LESSON_FILE)
    ]
    assert root.waves == [leaves]
    assert not set(root.one_by_one) & set(leaves)  # no leaf was read on its own


def test_an_http_root_reads_a_wave_all_at_once():
    """Pinned with a barrier rather than a stopwatch, like `tests/test_concurrency.py`: a root
    that walked the wave one path at a time would never trip it, and there is no timing
    threshold to tune on a slow machine. How many of these actually reach the origin at once
    is the gate's business (`tests/test_fetchers.py`)."""
    met = threading.Barrier(4, timeout=20)

    class BarrierRoot(HttpPackageRoot):
        def fetch(self, relative_path: str) -> bytes:
            met.wait()  # nobody answers until the whole wave has arrived
            return relative_path.encode()

    wave = ["a.md", "b.md", "c.md", "d.md"]
    assert BarrierRoot("https://a-course.learn-pack.com").fetch_all(wave) == {
        path: path.encode() for path in wave
    }


def test_a_package_is_the_same_package_however_its_root_reads_it():
    """The identity must not depend on which file answered first: the hash is taken over
    paths in sorted order and the artifact list is built in the declared one, so a root that
    fans out and a root that does not describe the same content."""

    class FanOutRoot(FilesystemPackageRoot):
        def fetch_all(self, relative_paths):
            paths = list(relative_paths)
            return dict(zip(paths, all_at_once(self.fetch, paths), strict=True))

    course = FIXTURES / "introduction-to-generative-ai"
    one_at_a_time = LearnpackV1Discovery().discover(FilesystemPackageRoot(course))
    together = LearnpackV1Discovery().discover(FanOutRoot(course))

    assert together.content_hash == one_at_a_time.content_hash
    assert together.artifacts == one_at_a_time.artifacts


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


@pytest.mark.parametrize(
    "locator",
    [
        "../outside.txt",
        "exercises/../../outside.txt",
        str(Path("/etc/passwd")),
    ],
)
def test_a_filesystem_root_refuses_a_locator_outside_its_base(tmp_path, locator):
    """ADR-0035 §7: the paths discovery fetches come from the package's own manifests, so
    containment cannot rest on whoever named the directory being careful."""
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    course = tmp_path / "course"
    course.mkdir()

    with pytest.raises(PackageDiscoveryError):
        FilesystemPackageRoot(course).fetch(locator)


def test_a_filesystem_root_still_reads_what_is_inside(tmp_path):
    course = tmp_path / "course"
    (course / "exercises").mkdir(parents=True)
    (course / "exercises" / "app.py").write_text("print(1)", encoding="utf-8")

    assert FilesystemPackageRoot(course).fetch("exercises/app.py") == b"print(1)"
