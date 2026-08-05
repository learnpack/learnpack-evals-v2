"""LearnpackV1 extraction adapter — deterministic, no LLM, no inference (ADR-0009).

What a LearnPack package actually offers (frozen in `tests/fixtures/learnpack_v1/`):
`learn.json` declares slug/title/technologies/difficulty/description — NO objectives,
audience or prerequisites as structured fields — and `.learn/package-manifest.json`
carries the authoritative `lessons[]` index (id, slug, position, type, title,
description). Lesson bodies live in `exercises/<slug>/README.md`; code exercises are
sibling files whose reference solution follows the `<stem>.solution.hide.<ext>`
convention (e.g. `app.py` / `app.solution.hide.py`). Therefore:

- `learning_objectives` / `target_audience` / `prerequisites` come from the content's
  DECLARED metadata (`declared_structured`) or are `absent` — they exist nowhere in the
  package itself, and reconstructing them from description prose would be inference.
- `lesson_inventory` is the manifest's `lessons[]`, verbatim fields only.
- `lesson_activities` is OBSERVED per lesson from the learner-facing component syntax
  (the generator's assessment-component catalog): multiple choice = task-list options
  with a `[x]` correct answer (one per question, so counting `[x]` lines counts
  questions); open question / select the blank / ordering / fill in the blank = fenced
  code blocks whose language is `question` / `select_the_blank` / `ordering` /
  `fill_in_the_blank` (the last one is a legacy component, per its retired spec: same
  fence syntax with per-blank answers as metadata; no frozen package exhibits it yet).
  `code_challenge_proposal` blocks are author-facing and deliberately NOT counted.
  Fences and checkboxes inside other fenced blocks are ignored.

For observed entries the citation is the extracted index serialized canonically; the
locator names the artifacts it was read from — every element is verifiable against them.

Artifact kinds the adapter understands (open vocabulary, this adapter's convention):
`manifest` (learn.json) · `package_manifest` (.learn/package-manifest.json) ·
`lesson_content` (exercises/<slug>/README.md — the slug is the locator's parent
directory, as in the real layout) · `lesson_file` (any other file in a lesson's
directory). Any artifact it chooses to read that cannot be fetched or parsed raises
`ExtractionError` → a `failed` profile, never a crash and never a half-profile.

Any change in this mapping is a new ADAPTER_VERSION: the version is the identity of the
extraction, and each one requires its own `ExtractionAccepted` act.
"""

import json
import re
from typing import Any

from app.modules.content_profiling.application.dtos import ArtifactDTO, PackageDTO
from app.modules.content_profiling.application.ports import PackageFetcherPort
from app.modules.content_profiling.domain.profile import (
    ExtractionError,
    ProfileEntry,
    ProfileExtra,
)

PACKAGE_FORMAT = "LearnpackV1"
ADAPTER_VERSION = "2"  # v1 extracted practice_exercises from .learn/config.json

CAPABILITIES = frozenset(
    {
        "learning_objectives",
        "target_audience",
        "prerequisites",
        "lesson_inventory",
        "lesson_activities",
    }
)

# Registry metadata key (camelCase, the seeded MetadataSchema) → data requirement id.
_METADATA_CAPABILITIES = {
    "learningObjectives": "learning_objectives",
    "targetAudience": "target_audience",
    "prerequisites": "prerequisites",
}

KIND_MANIFEST = "manifest"
KIND_PACKAGE_MANIFEST = "package_manifest"
KIND_LESSON_CONTENT = "lesson_content"
KIND_LESSON_FILE = "lesson_file"

# Fence language → activity key (the generator's assessment-component catalog).
_ACTIVITY_FENCES = {
    "question": "openQuestion",
    "select_the_blank": "selectTheBlank",
    "ordering": "ordering",
    "fill_in_the_blank": "fillInTheBlank",
}
_MCQ_CORRECT = re.compile(r"^- \[x\]", re.IGNORECASE)
_SOLUTION_MARKER = ".solution.hide."


def _quote(value: Any) -> str:
    """The verbatim citation of a declared value, serialized canonically (deterministic)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json(raw: bytes, locator: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractionError(f"artifact '{locator}' is not valid JSON: {exc}") from exc


def _decode_text(raw: bytes, locator: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(f"artifact '{locator}' is not UTF-8 text: {exc}") from exc


def _lesson_slug(locator: str) -> str:
    """The lesson a file belongs to — its parent directory in the package layout."""
    parts = locator.replace("\\", "/").rstrip("/").split("/")
    return parts[-2] if len(parts) >= 2 else ""


def _file_name(locator: str) -> str:
    return locator.replace("\\", "/").rstrip("/").split("/")[-1]


def _solution_name(exercise_file: str) -> str:
    """`app.py` → `app.solution.hide.py`: the marker goes before the extension."""
    if "." not in exercise_file:
        return exercise_file + _SOLUTION_MARKER.rstrip(".")
    stem, extension = exercise_file.rsplit(".", 1)
    return f"{stem}{_SOLUTION_MARKER}{extension}"


def _english(text_by_language: Any) -> str | None:
    """Pick the declared English text, else any declared translation — never composed."""
    if isinstance(text_by_language, str):
        return text_by_language
    if isinstance(text_by_language, dict) and text_by_language:
        english = text_by_language.get("en")
        if isinstance(english, str):
            return english
        first = next(iter(sorted(text_by_language)))
        value = text_by_language[first]
        return value if isinstance(value, str) else None
    return None


def _activity_counts(body: str) -> dict[str, int]:
    """Count learner-facing activities in a lesson body — pure line scanning, no parsing
    beyond the component syntax rules, and blind to anything inside foreign fences."""
    counts = {key: 0 for key in ("multipleChoice", *_ACTIVITY_FENCES.values())}
    inside_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if inside_fence:
                inside_fence = False
                continue
            language = stripped[3:].split(" ")[0].strip()
            activity = _ACTIVITY_FENCES.get(language)
            if activity is not None:
                counts[activity] += 1
            inside_fence = True
            continue
        if not inside_fence and _MCQ_CORRECT.match(stripped):
            counts["multipleChoice"] += 1
    return counts


class LearnpackV1Adapter:
    @property
    def package_format(self) -> str:
        return PACKAGE_FORMAT

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    @property
    def capabilities(self) -> frozenset[str]:
        return CAPABILITIES

    def extract(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> tuple[tuple[ProfileEntry, ...], tuple[ProfileExtra, ...]]:
        inventory = self._lesson_inventory(package, fetcher)
        entries = [
            *self._from_declared_metadata(package),
            inventory,
            self._lesson_activities(package, fetcher, inventory),
        ]
        return tuple(entries), self._extras(package, fetcher)

    # --- declared metadata (the registry's, ADR-0001) -----------------------------------

    def _from_declared_metadata(self, package: PackageDTO) -> list[ProfileEntry]:
        entries = []
        for key, requirement_id in _METADATA_CAPABILITIES.items():
            if key in package.declared_metadata:
                value = package.declared_metadata[key]
                entries.append(
                    ProfileEntry(
                        data_requirement_id=requirement_id,
                        provenance="declared_structured",
                        value=value,
                        quote=_quote(value),
                        locator={"source": "metadata", "key": key},
                    )
                )
            else:
                entries.append(
                    ProfileEntry(data_requirement_id=requirement_id, provenance="absent")
                )
        return entries

    # --- lesson inventory (the manifest's declared index) -------------------------------

    def _lesson_inventory(self, package: PackageDTO, fetcher: PackageFetcherPort) -> ProfileEntry:
        artifact = self._single_artifact(package, KIND_PACKAGE_MANIFEST)
        if artifact is None:
            return ProfileEntry(data_requirement_id="lesson_inventory", provenance="absent")

        manifest = _parse_json(fetcher.fetch(artifact.locator), artifact.locator)
        lessons = manifest.get("lessons") if isinstance(manifest, dict) else None
        if not isinstance(lessons, list):
            raise ExtractionError(f"artifact '{artifact.locator}' has no 'lessons' index")

        value = [
            {
                "lessonId": str(lesson.get("id", "")),
                "slug": str(lesson.get("slug", "")),
                "position": lesson.get("position"),
                "type": lesson.get("type"),
                "title": _english(lesson.get("title")),
                "description": _english(lesson.get("description")),
            }
            for lesson in lessons
            if isinstance(lesson, dict)
        ]
        return ProfileEntry(
            data_requirement_id="lesson_inventory",
            provenance="declared_structured",
            value=value,
            quote=_quote(value),
            locator={
                "source": "artifact",
                "kind": KIND_PACKAGE_MANIFEST,
                "locator": artifact.locator,
                "path": "$.lessons",
            },
        )

    # --- lesson activities (observed in the lesson bodies and files) --------------------

    def _lesson_activities(
        self, package: PackageDTO, fetcher: PackageFetcherPort, inventory: ProfileEntry
    ) -> ProfileEntry:
        contents = [a for a in package.artifacts if a.kind == KIND_LESSON_CONTENT]
        files = [a for a in package.artifacts if a.kind == KIND_LESSON_FILE]
        if not contents and not files:
            return ProfileEntry(data_requirement_id="lesson_activities", provenance="absent")

        id_by_slug: dict[str, str] = {}
        if inventory.provenance != "absent":
            id_by_slug = {lesson["slug"]: lesson["lessonId"] for lesson in inventory.value or []}

        counts_by_slug: dict[str, dict[str, int]] = {}
        for artifact in contents:
            body = _decode_text(fetcher.fetch(artifact.locator), artifact.locator)
            counts_by_slug[_lesson_slug(artifact.locator)] = _activity_counts(body)

        files_by_slug: dict[str, list[str]] = {}
        for artifact in files:
            files_by_slug.setdefault(_lesson_slug(artifact.locator), []).append(
                _file_name(artifact.locator)
            )

        empty = {key: 0 for key in ("multipleChoice", *_ACTIVITY_FENCES.values())}
        value = [
            {
                "lessonSlug": slug,
                "lessonId": id_by_slug.get(slug),
                "activities": counts_by_slug.get(slug, dict(empty)),
                "codeExercises": self._code_exercises(files_by_slug.get(slug, [])),
            }
            for slug in sorted(set(counts_by_slug) | set(files_by_slug))
        ]
        return ProfileEntry(
            data_requirement_id="lesson_activities",
            provenance="declared_structured",
            value=value,
            quote=_quote(value),
            locator={
                "source": "artifacts",
                "kinds": [KIND_LESSON_CONTENT, KIND_LESSON_FILE],
            },
        )

    @staticmethod
    def _code_exercises(file_names: list[str]) -> list[dict[str, Any]]:
        solutions = {name for name in file_names if _SOLUTION_MARKER in name}
        exercises = [
            name
            for name in sorted(file_names)
            if _SOLUTION_MARKER not in name and not name.startswith("README")
        ]
        return [
            {"file": name, "hasSolution": _solution_name(name) in solutions} for name in exercises
        ]

    # --- extras: non-canonical but useful on the designer's workbench (ADR-0012) --------

    def _extras(self, package: PackageDTO, fetcher: PackageFetcherPort) -> tuple[ProfileExtra, ...]:
        manifest_artifact = self._single_artifact(package, KIND_MANIFEST)
        if manifest_artifact is None:
            return ()
        manifest = _parse_json(fetcher.fetch(manifest_artifact.locator), manifest_artifact.locator)
        if not isinstance(manifest, dict):
            raise ExtractionError(f"artifact '{manifest_artifact.locator}' is not a JSON object")
        extras = []
        for field in ("difficulty", "technologies"):
            if field in manifest:
                extras.append(
                    ProfileExtra(
                        name=field,
                        value=manifest[field],
                        quote=_quote(manifest[field]),
                        locator={
                            "source": "artifact",
                            "kind": KIND_MANIFEST,
                            "locator": manifest_artifact.locator,
                            "path": f"$.{field}",
                        },
                    )
                )
        return tuple(extras)

    @staticmethod
    def _single_artifact(package: PackageDTO, kind: str) -> ArtifactDTO | None:
        return next((a for a in package.artifacts if a.kind == kind), None)
