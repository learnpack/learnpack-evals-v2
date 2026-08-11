"""`PackageDiscoveryPort` adapters: mechanical intake of the declared surface (ADR-0027).

Mirrors the brief intake's registry (ADR-0022): one discovery per `PackageFormat`,
registered in `DISCOVERIES_BY_FORMAT`; `PackageDiscovery` dispatches by format. Transport is
a separate axis — a `PackageRoot` (filesystem or HTTP) is injected, so one discovery reads a
package identically from any serving root.

This module is the sole writer of the artifact `kind` vocabulary. Discovery is hard-failing
on purpose (contrast with the brief intake's soft misses): a package whose manifests or
enumeration cannot be read is not registered — a mis-discovered package would *be* the
evaluand, wrong. Whether a format has a soft spot at all is the format's own business:
LearnpackV1 has exactly one, the syllabus, because packages legitimately lack it and its
absence is a first-class recorded state downstream (ADR-0022); LearnpackV2 has none,
because it embeds its commission unconditionally.
"""

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.modules.evaluand_registry.application.ports import (
    DiscoveredArtifact,
    DiscoveredPackage,
    PackageDiscoveryError,
)
from app.modules.evaluand_registry.infrastructure import acl_learnpack, acl_learnpack_v2
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher, HttpFetcher

# The artifact kind vocabulary (single writer: this module). The extraction adapter and the
# brief intake read these labels; a test pins the alignment. Each format writes its own
# vocabulary; `lesson_content` is shared because a lesson body is a lesson body.
KIND_MANIFEST = "manifest"
KIND_PACKAGE_MANIFEST = "package_manifest"
KIND_SYLLABUS = "syllabus"
KIND_LESSON_CONTENT = "lesson_content"
KIND_LESSON_FILE = "lesson_file"

MANIFEST_PATH = "learn.json"
PACKAGE_MANIFEST_PATH = ".learn/package-manifest.json"
CONFIG_PATH = ".learn/config.json"
SYLLABUS_PATH = ".learn/initialSyllabus.json"
LESSONS_DIR = "exercises"
LESSON_BODY_NAME = "README.md"

KIND_RUN_MANIFEST = "run_manifest"
KIND_USER_INTENT = "user_intent"
KIND_COURSE_VALUE = "course_value"
KIND_CONCEPT_GRAPH = "concept_graph"
KIND_COVERAGE_CHECK = "coverage_check"
KIND_COURSE_REQUEST = "course_request"
KIND_LESSON_PLAN = "lesson_plan"
KIND_LESSON_BRIEF = "lesson_brief"
KIND_LESSON_STATS = "lesson_stats"

V2_RUN_MANIFEST_PATH = "traces/run_metadata.json"
V2_USER_INTENT_PATH = "files/user_intent.json"
V2_COURSE_VALUE_PATH = "files/course_value.json"
V2_CONCEPT_GRAPH_PATH = "files/concept_graph.json"
V2_COVERAGE_CHECK_PATH = "files/coverage_check.json"
V2_COURSE_REQUEST_PATH = "files/course_request.json"
V2_LESSON_PLAN_PATH = "files/lesson_plan.json"
V2_LESSON_BRIEFS_DIR = "files/lesson_briefs"
V2_LESSON_STATS_DIR = "files/processing_stats"
V2_LESSONS_DIR = "lessons"


class PackageRoot(Protocol):
    """One package's serving root: fetch by root-relative path, and mint the locator that
    gets registered for that path. Keeping both on the root is what lets locators be mount
    URLs, plain relative paths (fixtures) or prefixed paths (seeder) without discovery
    knowing the difference."""

    def fetch(self, relative_path: str) -> bytes: ...

    def locator_for(self, relative_path: str) -> str: ...

    @property
    def consumable_url(self) -> str | None:
        """None unless the root IS a deployed instance of the course (ADR-0028)."""
        ...


class HttpPackageRoot:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._fetcher = HttpFetcher(timeout_seconds)

    def fetch(self, relative_path: str) -> bytes:
        try:
            return self._fetcher.fetch(self.locator_for(relative_path))
        except FetchError as exc:
            # A miss during discovery refuses the registration (hard-failing, ADR-0027).
            raise PackageDiscoveryError(str(exc)) from exc

    def locator_for(self, relative_path: str) -> str:
        return f"{self._base_url}/{relative_path}"

    @property
    def consumable_url(self) -> str | None:
        # The one case where transport and deployment coincide (ADR-0028): for a LearnPack
        # package the served root is the running course.
        return self._base_url


class FilesystemPackageRoot:
    """A package directory. `locator_base` prefixes the registered locators — a mount URL
    (local intake), a plain prefix like the course slug (seeder), or None for locators that
    are the relative paths themselves (fixtures). It is a locator prefix and nothing else."""

    def __init__(self, base_dir: Path, locator_base: str | None = None) -> None:
        self._fetcher = FilesystemFetcher(base_dir)
        self._locator_base = locator_base.rstrip("/") if locator_base else None

    def fetch(self, relative_path: str) -> bytes:
        try:
            return self._fetcher.fetch(relative_path)
        except FetchError as exc:
            raise PackageDiscoveryError(str(exc)) from exc

    def locator_for(self, relative_path: str) -> str:
        relative = Path(relative_path).as_posix()
        return f"{self._locator_base}/{relative}" if self._locator_base else relative

    @property
    def consumable_url(self) -> str | None:
        """None, always: serving a package's bytes — over the dev mount or anything else — is
        a transport arrangement, not a deployment (ADR-0028). The mount is what makes the
        locators fetchable; it never made the course consumable."""
        return None


def source_root(source_locator: str, locator_base: str | None = None) -> PackageRoot:
    """The default root for a source: http(s) locators are served roots, anything else is a
    directory. `locator_base` applies to directories only (http roots mint their own URLs)."""
    if source_locator.startswith(("http://", "https://")):
        return HttpPackageRoot(source_locator)
    return FilesystemPackageRoot(Path(source_locator), locator_base=locator_base)


class FormatPackageDiscoveryPort(Protocol):
    """What one format contributes: how to read its declared surface from a root."""

    package_format: str

    def discover(self, root: PackageRoot) -> DiscoveredPackage: ...


def _parse_json(raw: bytes, relative_path: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageDiscoveryError(f"'{relative_path}' is not valid JSON: {exc}") from exc


def _english(text_by_language: Any) -> str | None:
    """Pick the declared English text, else any declared translation — never composed.
    (Same rule as the extraction adapter's; not imported — modules do not cross.)"""
    if isinstance(text_by_language, str):
        return text_by_language
    if isinstance(text_by_language, dict) and text_by_language:
        english = text_by_language.get("en")
        if isinstance(english, str):
            return english
        first = next(iter(sorted(text_by_language)))
        value = text_by_language[first]
        if isinstance(value, str):
            return value
    return None


def _content_hash(fetched: dict[str, bytes]) -> str:
    """sha256 over `path:sha256(bytes)` lines sorted by root-relative path — the same
    package hashes identically from any serving root (ADR-0027). Changing this scheme is a
    compatibility event: old rows keep their old hashes (the column tolerates it), but
    cross-scheme dedupe stops working."""
    lines = (f"{path}:{hashlib.sha256(fetched[path]).hexdigest()}" for path in sorted(fetched))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


class LearnpackV1Discovery:
    """LearnpackV1: identity and descriptor from `learn.json`; the full exercise
    enumeration from `.learn/config.json` — lesson bodies in each exercise's
    `translations`, code files in its `files[]` — so no directory walking is needed and the
    same reading works over filesystem and HTTP."""

    package_format = acl_learnpack.PACKAGE_FORMAT

    def discover(self, root: PackageRoot) -> DiscoveredPackage:
        fetched: dict[str, bytes] = {}

        manifest_raw = root.fetch(MANIFEST_PATH)
        fetched[MANIFEST_PATH] = manifest_raw
        manifest = _parse_json(manifest_raw, MANIFEST_PATH)
        if not isinstance(manifest, dict):
            raise PackageDiscoveryError(f"'{MANIFEST_PATH}' is not a JSON object")
        slug = manifest.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            raise PackageDiscoveryError(f"'{MANIFEST_PATH}' declares no slug")

        fetched[PACKAGE_MANIFEST_PATH] = root.fetch(PACKAGE_MANIFEST_PATH)

        config_raw = root.fetch(CONFIG_PATH)
        fetched[CONFIG_PATH] = config_raw
        lesson_paths = self._lesson_paths(_parse_json(config_raw, CONFIG_PATH))

        artifacts = [
            DiscoveredArtifact(kind=KIND_MANIFEST, locator=root.locator_for(MANIFEST_PATH)),
            DiscoveredArtifact(
                kind=KIND_PACKAGE_MANIFEST, locator=root.locator_for(PACKAGE_MANIFEST_PATH)
            ),
        ]
        # Soft on purpose: packages legitimately lack a syllabus, and the brief then
        # registers absent (ADR-0022) — the one artifact whose absence is a recorded state.
        try:
            fetched[SYLLABUS_PATH] = root.fetch(SYLLABUS_PATH)
            artifacts.append(
                DiscoveredArtifact(kind=KIND_SYLLABUS, locator=root.locator_for(SYLLABUS_PATH))
            )
        except PackageDiscoveryError:
            pass

        for path in lesson_paths:
            fetched[path] = root.fetch(path)
            kind = (
                KIND_LESSON_CONTENT if path.endswith(f"/{LESSON_BODY_NAME}") else KIND_LESSON_FILE
            )
            artifacts.append(DiscoveredArtifact(kind=kind, locator=root.locator_for(path)))

        return DiscoveredPackage(
            package_format=self.package_format,
            external_id=slug,
            title=_english(manifest.get("title")),
            consumable_url=root.consumable_url,
            artifacts=tuple(artifacts),
            content_hash=_content_hash(fetched),
        )

    def _lesson_paths(self, config: Any) -> list[str]:
        """Every exercise file `.learn/config.json` declares, in declared order: the lesson
        bodies live in each exercise's `translations`, the code files in its `files[]` —
        `files[]` never lists the READMEs (verified against real packages)."""
        exercises = config.get("exercises") if isinstance(config, dict) else None
        if not isinstance(exercises, list):
            raise PackageDiscoveryError(f"'{CONFIG_PATH}' declares no exercises list")

        paths: list[str] = []
        for exercise in exercises:
            if not isinstance(exercise, dict):
                raise PackageDiscoveryError(f"'{CONFIG_PATH}' has a non-object exercise entry")
            slug = exercise.get("slug")
            if not isinstance(slug, str) or not slug.strip():
                raise PackageDiscoveryError(f"'{CONFIG_PATH}' has an exercise without a slug")

            names: list[str] = []
            translations = exercise.get("translations")
            if isinstance(translations, dict):
                names.extend(
                    name for name in translations.values() if isinstance(name, str) and name
                )
            for entry in exercise.get("files") or []:
                name = entry.get("name") if isinstance(entry, dict) else None
                if isinstance(name, str) and name:
                    names.append(name)

            seen: set[str] = set()
            for name in names:
                if name not in seen:
                    seen.add(name)
                    paths.append(f"{LESSONS_DIR}/{slug}/{name}")
        return paths


class LearnpackV2Discovery:
    """LearnpackV2: a generator run's output tree, not a runnable course.

    Identity is composed rather than declared — the tree carries no slug — from the two
    things `traces/run_metadata.json` states about the run: which seed it was started from
    and when. The full lesson enumeration comes from `files/lesson_plan.json`, which lists
    lesson **ids**, not filenames; each id's `files/processing_stats/<id>.json` declares the
    `lesson_slug` that names its body under `lessons/`. So the tree is read without ever
    listing a directory, exactly like V1 and for the same reason: a `PackageRoot` fetches by
    path and nothing more, over filesystem or HTTP alike.

    The declared surface is the course plus the evidence of how it was generated. The run's
    `logs/` and the generator's `config/` are deliberately outside it: one is run telemetry
    down to absolute paths on the machine that produced it, the other is the generator
    describing itself (ADR-0030), and neither is the evaluand.
    """

    package_format = acl_learnpack_v2.PACKAGE_FORMAT

    def discover(self, root: PackageRoot) -> DiscoveredPackage:
        fetched: dict[str, bytes] = {}
        artifacts: list[DiscoveredArtifact] = []

        def take(path: str, kind: str) -> bytes:
            raw = root.fetch(path)
            fetched[path] = raw
            artifacts.append(DiscoveredArtifact(kind=kind, locator=root.locator_for(path)))
            return raw

        manifest = _parse_json(take(V2_RUN_MANIFEST_PATH, KIND_RUN_MANIFEST), V2_RUN_MANIFEST_PATH)
        external_id = self._external_id(manifest)

        take(V2_USER_INTENT_PATH, KIND_USER_INTENT)
        take(V2_COURSE_VALUE_PATH, KIND_COURSE_VALUE)
        take(V2_CONCEPT_GRAPH_PATH, KIND_CONCEPT_GRAPH)
        take(V2_COVERAGE_CHECK_PATH, KIND_COVERAGE_CHECK)
        take(V2_COURSE_REQUEST_PATH, KIND_COURSE_REQUEST)

        plan = _parse_json(take(V2_LESSON_PLAN_PATH, KIND_LESSON_PLAN), V2_LESSON_PLAN_PATH)

        for lesson_id in self._lesson_ids(plan):
            take(f"{V2_LESSON_BRIEFS_DIR}/{lesson_id}.json", KIND_LESSON_BRIEF)
            stats_path = f"{V2_LESSON_STATS_DIR}/{lesson_id}.json"
            slug = self._lesson_slug(_parse_json(take(stats_path, KIND_LESSON_STATS), stats_path))
            take(f"{V2_LESSONS_DIR}/{slug}.md", KIND_LESSON_CONTENT)

        return DiscoveredPackage(
            package_format=self.package_format,
            external_id=external_id,
            title=plan.get("course_title") if isinstance(plan, dict) else None,
            consumable_url=root.consumable_url,
            artifacts=tuple(artifacts),
            content_hash=_content_hash(fetched),
        )

    def _external_id(self, manifest: Any) -> str:
        """`<seed>-<run start>`: which instruction produced this course, and which run of it.

        The seed alone would collide across regenerations; the timestamp alone says nothing
        about what was asked. `started_at` is the run's own declaration, so the id survives
        the tree being moved, renamed or served from anywhere — which the directory name,
        the other obvious candidate, would not.
        """
        if not isinstance(manifest, dict):
            raise PackageDiscoveryError(f"'{V2_RUN_MANIFEST_PATH}' is not a JSON object")
        run_info = (manifest.get("system_metadata") or {}).get("run_info")
        seed_id = run_info.get("seed_id") if isinstance(run_info, dict) else None
        if not isinstance(seed_id, str) or not seed_id.strip():
            raise PackageDiscoveryError(f"'{V2_RUN_MANIFEST_PATH}' declares no run seed id")

        started_at = manifest.get("started_at")
        if not isinstance(started_at, str):
            raise PackageDiscoveryError(f"'{V2_RUN_MANIFEST_PATH}' declares no run start")
        try:
            started = datetime.fromisoformat(started_at)
        except ValueError as exc:
            raise PackageDiscoveryError(
                f"'{V2_RUN_MANIFEST_PATH}' declares an unreadable run start '{started_at}': {exc}"
            ) from exc
        # Normalized to UTC so the same run reads the same id wherever it is discovered; a
        # declaration without an offset is taken at face value, not localized.
        if started.tzinfo is not None:
            started = started.astimezone(UTC)

        return f"{seed_id.strip()}-{started.strftime('%Y%m%d%H%M%S')}"

    def _lesson_ids(self, plan: Any) -> list[str]:
        lessons = plan.get("lessons") if isinstance(plan, dict) else None
        if not isinstance(lessons, list):
            raise PackageDiscoveryError(f"'{V2_LESSON_PLAN_PATH}' declares no lessons list")

        ids: list[str] = []
        for lesson in lessons:
            if not isinstance(lesson, dict):
                raise PackageDiscoveryError(f"'{V2_LESSON_PLAN_PATH}' has a non-object lesson")
            lesson_id = lesson.get("id")
            if not isinstance(lesson_id, str) or not lesson_id.strip():
                raise PackageDiscoveryError(f"'{V2_LESSON_PLAN_PATH}' has a lesson without an id")
            ids.append(lesson_id)
        return ids

    def _lesson_slug(self, stats: Any) -> str:
        """The stats file is what names the lesson body — the plan never does."""
        slug = stats.get("lesson_slug") if isinstance(stats, dict) else None
        if not isinstance(slug, str) or not slug.strip():
            raise PackageDiscoveryError(
                f"a file in '{V2_LESSON_STATS_DIR}' declares no lesson_slug"
            )
        return slug


DISCOVERIES_BY_FORMAT: dict[str, FormatPackageDiscoveryPort] = {
    discovery.package_format: discovery
    for discovery in (LearnpackV1Discovery(), LearnpackV2Discovery())
}


class PackageDiscovery:
    """`PackageDiscoveryPort`: dispatch to the format's discovery over the source's root."""

    def __init__(
        self,
        root_factory: Callable[[str], PackageRoot] = source_root,
        discoveries: Mapping[str, FormatPackageDiscoveryPort] = DISCOVERIES_BY_FORMAT,
    ) -> None:
        self._root_factory = root_factory
        self._discoveries = discoveries

    def discover(self, package_format: str, source_locator: str) -> DiscoveredPackage:
        discovery = self._discoveries.get(package_format)
        if discovery is None:
            raise PackageDiscoveryError(f"no discovery is registered for format '{package_format}'")
        return discovery.discover(self._root_factory(source_locator))
