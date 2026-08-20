"""LearnpackV1 extraction adapter — deterministic, no LLM, no inference (ADR-0009).

What a LearnPack package actually offers (frozen in `tests/fixtures/learnpack_v1/`):
`learn.json` declares slug/title/technologies/difficulty/description — NO objectives,
audience or prerequisites as structured fields — and `.learn/package-manifest.json`
carries the authoritative `lessons[]` index (id, slug, position, type, title,
description). Lesson bodies live in `exercises/<slug>/README.md`; code exercises are
sibling files, optionally accompanied by an internal reference solution named
`<stem>.solution.hide.<ext>` (e.g. `app.solution.hide.py`) — internal, not
learner-facing, so solution files never count as exercises. Therefore:

- There is NO capability for objectives, audience or prerequisites: the package declares
  them nowhere (and the registry metadata channel is gone, ADR-0017), so criteria that
  require them derive `not_applicable` — unmet demand for this format, surfaced by
  matching/readiness. When the generator starts declaring them in the package, a new
  ADAPTER_VERSION will claim the capability.
- `course_descriptor` is what `learn.json` declares about the whole course. `difficulty`
  is the closest this format has to a declared level, which is why it is canonical data
  and no longer a workbench extra.
- `lesson_assessment_items` is the same components `lesson_activities` counts, kept
  VERBATIM instead of tallied: a multiple-choice item is a prompt plus its task-list
  options with the `[x]` marked; a fenced component's prompt is the prose introducing it,
  because the fence body holds the author's expected answers, not the question. A package
  with no items at all yields an `absent` entry, so a course without assessment reports
  `no_evidence` rather than an empty pass.
- Readability is NOT extracted, though every lesson's frontmatter offers a `fkglResult`.
  It is a generation-time snapshot that no longer matches the delivered body, and the
  measure that replaced it is computed by the assessor. See `docs/MEASUREMENT.md` before
  reaching for it.
- `lesson_inventory` is the manifest's `lessons[]`, verbatim fields only — WITHOUT the
  descriptions: those are machine-generated summaries projected from the syllabus, not
  the generator's declaration, so they are not evidence (ADR-0009).
- `lesson_bodies` is each lesson's learner-facing markdown body verbatim (frontmatter
  stripped, `declared_in_content` — the content citing itself): the evidence base for
  every judgment about what the lessons actually develop.
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
`lesson_content` (exercises/<slug>/README.md) · `lesson_file` (any other file in a
lesson's directory). A lesson artifact is one sitting DIRECTLY under `exercises/<slug>/`,
checked structurally rather than trusted from its kind: a misclassified artifact from
elsewhere in the package would otherwise invent a lesson named after whatever directory
it happened to live in. Any artifact it chooses to read that cannot be fetched or parsed
raises `ExtractionError` → a `failed` profile, never a crash and never a half-profile.

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
# Renumbered from "2" back to "1" while the whole slice was still development: no study
# had been published, so no adapter version was a reproducibility commitment yet. This "1"
# is NOT the original one (that one read practice_exercises from .learn/config.json).
ADAPTER_VERSION = "1"

CAPABILITIES = frozenset(
    {
        "course_descriptor",
        "lesson_inventory",
        "lesson_bodies",
        "lesson_activities",
        "lesson_assessment_items",
    }
)

KIND_MANIFEST = "manifest"
KIND_PACKAGE_MANIFEST = "package_manifest"
KIND_LESSON_CONTENT = "lesson_content"
KIND_LESSON_FILE = "lesson_file"

# The directory every lesson lives directly under, in this format's layout.
LESSONS_DIR = "exercises"

# Fence language → activity key (the generator's assessment-component catalog).
_ACTIVITY_FENCES = {
    "question": "openQuestion",
    "select_the_blank": "selectTheBlank",
    "ordering": "ordering",
    "fill_in_the_blank": "fillInTheBlank",
}
_MCQ_CORRECT = re.compile(r"^- \[x\]", re.IGNORECASE)
_MCQ_OPTION = re.compile(r"^-\s+\[([ xX])\]\s*(.*)$")
# Substring, not a dotted marker: `app.solution.hide.py` is the convention, but a file
# named `solution.hide.py` is just as internal and must not count as an exercise.
_SOLUTION_MARKER = "solution.hide"
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico")


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


def _lesson_slug(locator: str) -> str | None:
    """The lesson a file belongs to — its parent directory, and only when that directory
    sits directly under the package's `exercises/`.

    Structural on purpose: an artifact's `kind` is assigned at registration and can be
    wrong. Trusting it would let `.learn/assets/cover.png`, classified as a lesson file,
    invent a lesson called `assets` and give it a code exercise. `None` means "not a
    lesson artifact", whatever it was labelled."""
    parts = locator.replace("\\", "/").rstrip("/").split("/")
    if len(parts) < 3 or parts[-3] != LESSONS_DIR:
        return None
    return parts[-2]


def _file_name(locator: str) -> str:
    return locator.replace("\\", "/").rstrip("/").split("/")[-1]


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


def _strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block; what remains is the learner-facing body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])
    return text


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


def _plain(text: str) -> str:
    """A prompt as the learner reads it: the markdown scaffolding around it removed, the
    words untouched."""
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^\d+\.\s*", "", text)
    return re.sub(r"\*\*|__|`", "", text).strip()


def _assessment_items(body: str) -> list[dict[str, Any]]:
    """The lesson's assessment items, verbatim — the same components `_activity_counts`
    tallies, kept whole.

    A multiple-choice item is a prompt followed by task-list options, the correct ones
    marked `[x]`; its prompt is the last prose line before the options. A fenced component
    carries the author's expected answers inside the fence, not the question, so its
    prompt is the prose that introduces it."""
    items: list[dict[str, Any]] = []
    inside_fence = False
    last_prose = ""
    prompt = ""
    options: list[str] = []
    correct = 0

    def flush() -> None:
        nonlocal prompt, options, correct
        if options:
            items.append(
                {
                    "kind": "multipleChoice",
                    "prompt": prompt,
                    "options": options,
                    "correctCount": correct,
                }
            )
        prompt, options, correct = "", [], 0

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            if inside_fence:
                inside_fence = False
                continue
            language = stripped[3:].split(" ")[0].strip()
            activity = _ACTIVITY_FENCES.get(language)
            if activity is not None:
                items.append(
                    {"kind": activity, "prompt": last_prose, "options": [], "correctCount": 0}
                )
            inside_fence = True
            continue
        if inside_fence:
            continue
        option = _MCQ_OPTION.match(stripped)
        if option is not None:
            if not options:
                prompt = last_prose
            options.append(option.group(2).strip())
            correct += option.group(1).lower() == "x"
            continue
        flush()
        if stripped:
            last_prose = _plain(stripped)
    flush()
    return items


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
        texts_by_slug = self._lesson_texts(package, fetcher)  # fetched once, used thrice
        entries = [
            self._course_descriptor(package, fetcher),
            inventory,
            self._lesson_bodies(texts_by_slug, inventory),
            self._lesson_activities(package, texts_by_slug, inventory),
            self._lesson_assessment_items(texts_by_slug, inventory),
        ]
        # No extras: difficulty and technologies used to travel as workbench-only values,
        # and they are canonical `course_descriptor` fields now — one place, consumable.
        return tuple(entries), ()

    # --- course descriptor (what the manifest declares about the whole course) ----------

    def _course_descriptor(self, package: PackageDTO, fetcher: PackageFetcherPort) -> ProfileEntry:
        artifact = self._single_artifact(package, KIND_MANIFEST)
        if artifact is None:
            return ProfileEntry(data_requirement_id="course_descriptor", provenance="absent")

        manifest = _parse_json(fetcher.fetch(artifact.locator), artifact.locator)
        if not isinstance(manifest, dict):
            raise ExtractionError(f"artifact '{artifact.locator}' is not a JSON object")

        technologies = manifest.get("technologies")
        difficulty = manifest.get("difficulty")
        value = {
            "slug": str(manifest.get("slug", "")),
            "title": _english(manifest.get("title")),
            "description": _english(manifest.get("description")),
            "technologies": (
                [str(t) for t in technologies] if isinstance(technologies, list) else []
            ),
            "difficulty": difficulty if isinstance(difficulty, str) else None,
        }
        return ProfileEntry(
            data_requirement_id="course_descriptor",
            provenance="declared_structured",
            value=value,
            quote=_quote(value),
            locator={
                "source": "artifact",
                "kind": KIND_MANIFEST,
                "locator": artifact.locator,
                "path": "$",
            },
        )

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
            # No description on purpose: the manifest's descriptions are LLM-generated
            # summaries projected from the syllabus — not evidence (ADR-0009).
            {
                "lessonId": str(lesson.get("id", "")),
                "slug": str(lesson.get("slug", "")),
                "position": lesson.get("position"),
                "type": lesson.get("type"),
                "title": _english(lesson.get("title")),
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

    # --- lesson bodies and activities (observed in the lesson content) ------------------

    def _lesson_texts(self, package: PackageDTO, fetcher: PackageFetcherPort) -> dict[str, str]:
        """Raw lesson-content text by slug — fetched once, feeds bodies, activities and
        assessment items. Artifacts that do not sit under `exercises/<slug>/` are not
        lesson content whatever their kind says, and are not fetched at all.

        Asked for together: a lesson body is never read to find another one."""
        slug_by_locator: dict[str, str] = {}
        for artifact in package.artifacts:
            if artifact.kind != KIND_LESSON_CONTENT:
                continue
            slug = _lesson_slug(artifact.locator)
            if slug is not None:
                slug_by_locator[artifact.locator] = slug

        raw = fetcher.fetch_all(list(slug_by_locator))
        return {
            slug: _decode_text(raw[locator], locator) for locator, slug in slug_by_locator.items()
        }

    def _lesson_bodies(
        self, texts_by_slug: dict[str, str], inventory: ProfileEntry
    ) -> ProfileEntry:
        if not texts_by_slug:
            return ProfileEntry(data_requirement_id="lesson_bodies", provenance="absent")
        id_by_slug = self._id_by_slug(inventory)
        value = [
            {
                "lessonSlug": slug,
                "lessonId": id_by_slug.get(slug),
                "body": _strip_frontmatter(texts_by_slug[slug]),
            }
            for slug in sorted(texts_by_slug)
        ]
        return ProfileEntry(
            data_requirement_id="lesson_bodies",
            # The content citing itself: the body IS the evidence, verbatim.
            provenance="declared_in_content",
            value=value,
            quote=_quote(value),
            locator={"source": "artifacts", "kinds": [KIND_LESSON_CONTENT]},
        )

    def _lesson_activities(
        self, package: PackageDTO, texts_by_slug: dict[str, str], inventory: ProfileEntry
    ) -> ProfileEntry:
        files = [a for a in package.artifacts if a.kind == KIND_LESSON_FILE]
        if not texts_by_slug and not files:
            return ProfileEntry(data_requirement_id="lesson_activities", provenance="absent")

        id_by_slug = self._id_by_slug(inventory)
        counts_by_slug = {slug: _activity_counts(text) for slug, text in texts_by_slug.items()}

        files_by_slug: dict[str, list[str]] = {}
        for artifact in files:
            slug = _lesson_slug(artifact.locator)
            if slug is None:
                continue
            files_by_slug.setdefault(slug, []).append(_file_name(artifact.locator))

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
    def _id_by_slug(inventory: ProfileEntry) -> dict[str, str]:
        if inventory.provenance == "absent":
            return {}
        return {lesson["slug"]: lesson["lessonId"] for lesson in inventory.value or []}

    @staticmethod
    def _code_exercises(file_names: list[str]) -> list[str]:
        """Learner-facing exercise files only — everything else in a lesson's directory is
        something other than practice.

        Nothing here keys on a filename: the exercise is `app.py` in one course,
        `index.html` or `about_me.html` in another, and a rule that assumed one of those
        would report no practice at all for the others. What IS excluded is what cannot be
        an exercise: the lesson text, the internal `solution.hide` companions (authoring
        detail — the AI evaluator works from the lesson body alone), and images."""
        return [
            name
            for name in sorted(file_names)
            if _SOLUTION_MARKER not in name.lower()
            and "readme" not in name.lower()
            and not name.lower().endswith(_IMAGE_SUFFIXES)
        ]

    # --- assessment items (the same components, kept whole instead of tallied) ----------

    def _lesson_assessment_items(
        self, texts_by_slug: dict[str, str], inventory: ProfileEntry
    ) -> ProfileEntry:
        id_by_slug = self._id_by_slug(inventory)
        value = [
            {
                "lessonSlug": slug,
                "lessonId": id_by_slug.get(slug),
                "kind": item["kind"],
                "prompt": item["prompt"],
                "options": item["options"],
                "correctCount": item["correctCount"],
            }
            for slug in sorted(texts_by_slug)
            for item in _assessment_items(_strip_frontmatter(texts_by_slug[slug]))
        ]
        if not value:
            # The adapter looked and there was nothing: a course with no assessment cannot
            # evidence a claim about its assessment, and says so as `absent` (ADR-0009) —
            # an empty list would read as "assessment exists and is empty".
            return ProfileEntry(data_requirement_id="lesson_assessment_items", provenance="absent")
        return ProfileEntry(
            data_requirement_id="lesson_assessment_items",
            provenance="declared_structured",
            value=value,
            quote=_quote(value),
            locator={"source": "artifacts", "kinds": [KIND_LESSON_CONTENT]},
        )

    @staticmethod
    def _single_artifact(package: PackageDTO, kind: str) -> ArtifactDTO | None:
        return next((a for a in package.artifacts if a.kind == kind), None)
