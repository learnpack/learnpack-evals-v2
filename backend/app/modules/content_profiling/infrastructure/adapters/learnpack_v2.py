"""LearnpackV2 extraction adapter — deterministic, no LLM, no inference (ADR-0009).

A LearnpackV2 package is a generator run's output tree, **before** the teacher's processing
step (frozen in `tests/fixtures/learnpack_v2/`). That stage difference is what decides most
of what follows:

- `files/course_value.json` declares `learning_objectives[].outcome` and
  `files/user_intent.json` declares `target_audience`, both as structured fields. So this
  format supplies two capabilities LearnpackV1 cannot, and the criteria that require them
  stop deriving `not_applicable`.
- There is NO capability for `lesson_activities`. The format carries *proposals*, not
  exercises: a `code_challenge_proposal` block is the prompt a teacher will later use to
  generate the exercise files, and no exercise file exists yet. Supplying the requirement
  with an empty `codeExercises` would not be honest reporting — two of the criteria that
  read it declare `on_missing_evidence: fail`, so an empty list derives a **fail** for a
  defect that does not exist. Declaring no capability derives `not_applicable` instead
  (`evaluation/domain/derivation.py`, cases b vs c), which is the true statement: this
  format cannot answer that question. Proposals get their own id when an instrument mints
  one; until then they are not evidence for anything.
- There is NO capability for `prerequisites`. `concept_graph[].prerequisites` are
  prerequisites *between concepts inside the course*, not the prior knowledge a learner
  needs to start it. Mapping one to the other would be inference.

Counts are read from the lesson **bodies**, never from `files/processing_stats/*.json`.
The stats are a faithful record of the run — they even mark components the generator failed
to emit, with `component_retries[].resolved: false` — but the body is what is delivered, and
`lesson_assessment_items` needs one entry per QUESTION while the stats count COMPONENTS: a
single quiz block legitimately holds several questions. The stats are still read, for the
one thing they alone declare: which file holds each lesson id.

The component syntax this format uses (its own convention, verified against real packages):
`question` and `fill_in_the_blank` fences, and quizzes as an indented task list — a question
as a list item, a blank line, then options indented 3–6 spaces with a single `[x]`. That
indentation is the format's contract with the markdown renderer, so a task list outside that
range is not a quiz the learner would ever see and is not counted as one. LearnpackV1 anchors
its quizzes at column 0; the two conventions are both valid and deliberately not shared.

`code_challenge_proposal`, `mermaid` diagrams, illustration prompts and Rigo links are not
assessment items. The first two are author-facing, and the illustration's alt text is a
prompt for generating an image rather than a caption.

Artifact kinds the adapter reads (written by discovery, ADR-0027): `run_manifest` ·
`lesson_plan` · `course_value` · `user_intent` · `lesson_stats` · `lesson_content`. Any
artifact it chooses to read that cannot be fetched or parsed raises `ExtractionError` → a
`failed` profile, never a half-profile.

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

PACKAGE_FORMAT = "LearnpackV2"
ADAPTER_VERSION = "1"

CAPABILITIES = frozenset(
    {
        "course_descriptor",
        "lesson_inventory",
        "lesson_bodies",
        "lesson_assessment_items",
        "learning_objectives",
        "target_audience",
    }
)

KIND_RUN_MANIFEST = "run_manifest"
KIND_LESSON_PLAN = "lesson_plan"
KIND_COURSE_VALUE = "course_value"
KIND_USER_INTENT = "user_intent"
KIND_LESSON_STATS = "lesson_stats"
KIND_LESSON_CONTENT = "lesson_content"

# Fence language → assessment item kind. Same vocabulary LearnpackV1 reports, so a criterion
# reading `kind` reads one word for one thing across formats.
_ITEM_FENCES = {"question": "openQuestion", "fill_in_the_blank": "fillInTheBlank"}

# A quiz option: a task-list item indented 3 to 6 spaces, per the component's own spec —
# outside that range the markdown does not render as a quiz, so it is not one.
_QUIZ_OPTION = re.compile(r"^ {3,6}- \[([ xX])\]\s*(.*)$")
# The line a quiz hangs from: a list item, numbered or bulleted, at a shallower indent.
_QUESTION_ITEM = re.compile(r"^ {0,2}(?:\d+\.|[-*])\s+(.+)$")


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


def _file_stem(locator: str) -> str:
    """A lesson body's slug is its file name without the extension — the name the run's
    stats declared for it."""
    name = locator.replace("\\", "/").rstrip("/").split("/")[-1]
    return name[:-3] if name.endswith(".md") else name


def _plain(text: str) -> str:
    """A prompt as the learner reads it: the markdown scaffolding around it removed, the
    words untouched."""
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^(?:\d+\.|[-*])\s*", "", text)
    return re.sub(r"\*\*|__|`", "", text).strip()


def _assessment_items(body: str) -> list[dict[str, Any]]:
    """A lesson's assessment items, verbatim — pure line scanning, blind to anything inside
    a fence.

    A quiz item is one question: its options are grouped under the list item they hang from,
    so a single quiz block holding several questions yields several items. `correctCount` is
    whatever the group marks — a group with two `[x]` reports two rather than being discarded,
    because reporting is the adapter's job and judging is the criterion's.

    A fenced component carries the author's expected answers inside the fence, not the
    question, so its prompt is the prose that introduces it (the same rule LearnpackV1 uses).
    """
    items: list[dict[str, Any]] = []
    inside_fence = False
    last_prose = ""
    question = ""
    options: list[str] = []
    correct = 0

    def flush() -> None:
        nonlocal question, options, correct
        if options:
            items.append(
                {
                    "kind": "multipleChoice",
                    "prompt": question,
                    "options": options,
                    "correctCount": correct,
                }
            )
        question, options, correct = "", [], 0

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            if inside_fence:
                inside_fence = False
                continue
            language = stripped[3:].split(" ")[0].strip()
            kind = _ITEM_FENCES.get(language)
            if kind is not None:
                items.append({"kind": kind, "prompt": last_prose, "options": [], "correctCount": 0})
            inside_fence = True
            continue
        if inside_fence:
            continue

        option = _QUIZ_OPTION.match(line)
        if option is not None:
            if not options:
                question = last_prose
            options.append(option.group(2).strip())
            correct += option.group(1).lower() == "x"
            continue

        # A blank line sits between a question and its options by convention, so it must not
        # close a group that has not started yet — but any other content does.
        if not stripped:
            continue
        flush()
        item = _QUESTION_ITEM.match(line)
        last_prose = _plain(item.group(1) if item else stripped)
    flush()
    return items


class LearnpackV2Adapter:
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
        slug_by_id = self._slug_by_lesson_id(package, fetcher)
        texts_by_slug = self._lesson_texts(package, fetcher)  # fetched once, used twice
        inventory = self._lesson_inventory(package, fetcher, slug_by_id)
        entries = [
            self._course_descriptor(package, fetcher),
            inventory,
            self._lesson_bodies(texts_by_slug, inventory),
            self._lesson_assessment_items(texts_by_slug, inventory),
            self._learning_objectives(package, fetcher),
            self._target_audience(package, fetcher),
        ]
        return tuple(entries), ()

    # --- course descriptor (what the run declares about the whole course) ---------------

    def _course_descriptor(self, package: PackageDTO, fetcher: PackageFetcherPort) -> ProfileEntry:
        manifest_artifact = self._single_artifact(package, KIND_RUN_MANIFEST)
        plan_artifact = self._single_artifact(package, KIND_LESSON_PLAN)
        intent_artifact = self._single_artifact(package, KIND_USER_INTENT)
        if manifest_artifact is None or plan_artifact is None:
            return ProfileEntry(data_requirement_id="course_descriptor", provenance="absent")

        manifest = self._json_object(manifest_artifact, fetcher)
        run_info = manifest.get("system_metadata") or {}
        run_info = run_info.get("run_info") if isinstance(run_info, dict) else None
        seed_id = run_info.get("seed_id") if isinstance(run_info, dict) else None

        plan = self._json_object(plan_artifact, fetcher)
        title = plan.get("course_title")

        difficulty = None
        if intent_artifact is not None:
            declared = self._json_object(intent_artifact, fetcher).get("difficulty")
            difficulty = declared if isinstance(declared, str) else None

        value: dict[str, Any] = {
            "slug": str(seed_id) if isinstance(seed_id, str) else "",
            "title": title if isinstance(title, str) else None,
            # The format declares neither: a course description is written by the teacher
            # downstream, and technologies are not part of what a run records. Empty, not
            # guessed — `[]` is what "declares none" looks like in a non-nullable list.
            "description": None,
            "technologies": [],
            "difficulty": difficulty,
        }
        return ProfileEntry(
            data_requirement_id="course_descriptor",
            provenance="declared_structured",
            value=value,
            quote=_quote(value),
            locator={
                "source": "artifacts",
                "kinds": [KIND_RUN_MANIFEST, KIND_LESSON_PLAN, KIND_USER_INTENT],
            },
        )

    # --- lesson inventory (the plan's declared index, named by the run's stats) ---------

    def _slug_by_lesson_id(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> dict[str, str]:
        """Which file holds each lesson id — the one thing only the stats declare. The plan
        lists ids and never names a file."""
        slugs: dict[str, str] = {}
        for artifact in package.artifacts:
            if artifact.kind != KIND_LESSON_STATS:
                continue
            stats = self._json_object(artifact, fetcher)
            lesson_id, slug = stats.get("lesson_id"), stats.get("lesson_slug")
            if isinstance(lesson_id, str) and isinstance(slug, str):
                slugs[lesson_id] = slug
        return slugs

    def _lesson_inventory(
        self, package: PackageDTO, fetcher: PackageFetcherPort, slug_by_id: dict[str, str]
    ) -> ProfileEntry:
        artifact = self._single_artifact(package, KIND_LESSON_PLAN)
        if artifact is None:
            return ProfileEntry(data_requirement_id="lesson_inventory", provenance="absent")

        plan = self._json_object(artifact, fetcher)
        lessons = plan.get("lessons")
        if not isinstance(lessons, list):
            raise ExtractionError(f"artifact '{artifact.locator}' has no 'lessons' index")

        value = [
            {
                "lessonId": str(lesson.get("id", "")),
                "slug": slug_by_id.get(str(lesson.get("id", "")), ""),
                # The order the plan declares, read as declared — not composed from the id.
                "position": position,
                "type": lesson.get("type"),
                "title": lesson.get("title"),
            }
            for position, lesson in enumerate(lessons)
            if isinstance(lesson, dict)
        ]
        return ProfileEntry(
            data_requirement_id="lesson_inventory",
            provenance="declared_structured",
            value=value,
            quote=_quote(value),
            locator={
                "source": "artifacts",
                "kinds": [KIND_LESSON_PLAN, KIND_LESSON_STATS],
                "path": "$.lessons",
            },
        )

    # --- lesson bodies and the items observed in them -----------------------------------

    def _lesson_texts(self, package: PackageDTO, fetcher: PackageFetcherPort) -> dict[str, str]:
        return {
            _file_stem(artifact.locator): _decode_text(
                fetcher.fetch(artifact.locator), artifact.locator
            )
            for artifact in package.artifacts
            if artifact.kind == KIND_LESSON_CONTENT
        }

    def _lesson_bodies(
        self, texts_by_slug: dict[str, str], inventory: ProfileEntry
    ) -> ProfileEntry:
        if not texts_by_slug:
            return ProfileEntry(data_requirement_id="lesson_bodies", provenance="absent")
        id_by_slug = self._id_by_slug(inventory)
        # No frontmatter to strip: this format writes the body straight, opening on its
        # heading. Kept verbatim, which is what makes it evidence.
        value = [
            {"lessonSlug": slug, "lessonId": id_by_slug.get(slug), "body": texts_by_slug[slug]}
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
            for item in _assessment_items(texts_by_slug[slug])
        ]
        if not value:
            # The adapter looked and there was nothing: an empty list would read as
            # "assessment exists and is empty" (ADR-0009).
            return ProfileEntry(data_requirement_id="lesson_assessment_items", provenance="absent")
        return ProfileEntry(
            data_requirement_id="lesson_assessment_items",
            provenance="declared_in_content",
            value=value,
            quote=_quote(value),
            locator={"source": "artifacts", "kinds": [KIND_LESSON_CONTENT]},
        )

    # --- what the run declares about the commission it served ---------------------------

    def _learning_objectives(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> ProfileEntry:
        artifact = self._single_artifact(package, KIND_COURSE_VALUE)
        if artifact is None:
            return ProfileEntry(data_requirement_id="learning_objectives", provenance="absent")

        declared = self._json_object(artifact, fetcher).get("learning_objectives")
        objectives = [
            objective["outcome"]
            for objective in declared or []
            if isinstance(objective, dict) and isinstance(objective.get("outcome"), str)
        ]
        if not objectives:
            return ProfileEntry(data_requirement_id="learning_objectives", provenance="absent")
        return ProfileEntry(
            data_requirement_id="learning_objectives",
            provenance="declared_structured",
            value=objectives,
            quote=_quote(objectives),
            locator={
                "source": "artifact",
                "kind": KIND_COURSE_VALUE,
                "locator": artifact.locator,
                "path": "$.learning_objectives[*].outcome",
            },
        )

    def _target_audience(self, package: PackageDTO, fetcher: PackageFetcherPort) -> ProfileEntry:
        artifact = self._single_artifact(package, KIND_USER_INTENT)
        if artifact is None:
            return ProfileEntry(data_requirement_id="target_audience", provenance="absent")

        audience = self._json_object(artifact, fetcher).get("target_audience")
        if not isinstance(audience, str) or not audience.strip():
            # The format states what it was not told: `missing_fields` lists it explicitly,
            # and an absent entry is the same statement in the profile's vocabulary.
            return ProfileEntry(data_requirement_id="target_audience", provenance="absent")
        return ProfileEntry(
            data_requirement_id="target_audience",
            provenance="declared_structured",
            value=audience,
            quote=_quote(audience),
            locator={
                "source": "artifact",
                "kind": KIND_USER_INTENT,
                "locator": artifact.locator,
                "path": "$.target_audience",
            },
        )

    # --- reading helpers ----------------------------------------------------------------

    @staticmethod
    def _id_by_slug(inventory: ProfileEntry) -> dict[str, str]:
        if inventory.provenance == "absent":
            return {}
        return {lesson["slug"]: lesson["lessonId"] for lesson in inventory.value or []}

    @staticmethod
    def _single_artifact(package: PackageDTO, kind: str) -> ArtifactDTO | None:
        return next((a for a in package.artifacts if a.kind == kind), None)

    @staticmethod
    def _json_object(artifact: ArtifactDTO, fetcher: PackageFetcherPort) -> dict[str, Any]:
        parsed = _parse_json(fetcher.fetch(artifact.locator), artifact.locator)
        if not isinstance(parsed, dict):
            raise ExtractionError(f"artifact '{artifact.locator}' is not a JSON object")
        return parsed
