"""LearnpackV2 extraction adapter — deterministic, no LLM, no inference (ADR-0009).

A LearnpackV2 package is a generator run's output tree, **before** the teacher's processing
step (frozen in `tests/fixtures/learnpack_v2/`). That stage difference is what decides most
of what follows:

- `files/course_value.json` declares `learning_objectives[].outcome` and
  `files/user_intent.json` declares `target_audience`, both as structured fields. So this
  format supplies capabilities LearnpackV1 cannot, and the criteria that require them stop
  deriving `not_applicable`. Each objective also declares an id and a `verifiable_by` — the
  criterion by which it would be checked — which `declared_objectives` carries whole. That
  is what lets a criterion hold the assessment to what the objective itself promised, and
  it is why the same objectives travel under two ids: `learning_objectives` is consumed by
  criteria that count them, `declared_objectives` by criteria that compare against them.
- `files/lesson_plan.json` names the concept each lesson covers, which `lesson_concepts`
  carries in the plan's declared order — a course's trajectory without reading any body.
- There is NO capability for `lesson_activities`. The format carries *proposals*, not
  exercises: a `code_challenge_proposal` block is the prompt a teacher will later use to
  generate the exercise files, and no exercise file exists yet. Supplying the requirement
  with an empty `codeExercises` would not be honest reporting — two of the criteria that
  read it declare `on_missing_evidence: fail`, so an empty list derives a **fail** for a
  defect that does not exist. Declaring no capability derives `not_applicable` instead
  (`evaluation/domain/derivation.py`, cases b vs c), which is the true statement: this
  format cannot answer that question.
- Those proposals now have the id this docstring said they would get when an instrument
  minted one: `assessment_offerings` (ADR-0046) carries everything the package offers to
  assess with — the components that ship ready for the learner and the exercises it
  proposes for a later step to build — with every entry marked `delivered` or `proposed`.
  Marked rather than merged, and merged rather than split: a criterion that must tell the
  two apart reads the mark, while a criterion asking what the package commits to measuring
  is not silenced by a package that happens to offer only one of the two kinds. It does not
  replace `lesson_assessment_items`, which stays exactly what it was — the delivered half —
  and is what the other lineage's criteria require. `lesson_activities` is untouched by all
  of this: a proposal is a commitment to assess, not an exercise whose scaffolding anyone
  can read.
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

A `code_challenge_proposal` is never a **delivered** item: nothing in it is something a
learner can answer as it stands, so it stays out of `lesson_assessment_items` and travels in
`assessment_offerings` marked `proposed`. `mermaid` diagrams, illustration prompts and Rigo
links are not assessment at all, under either id — a diagram is author-facing, and the
illustration's alt text is a prompt for generating an image rather than a caption.

A proposal's prompt is the fence's OWN text, where a `question` fence's prompt is the prose
that introduces it. The asymmetry is the format's, not a choice: inside a `question` fence
the author writes the expected answers, while a proposal fence holds the instruction itself.

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
# 3: supplies `assessment_offerings`, the demand course-drafts-qa v7 mints so that what a
# draft PROPOSES to be assessed on stops being invisible (ADR-0046).
# 2: supplied `declared_objectives` and `lesson_concepts`, the demand course-drafts-qa v2
# mints for the constructive-alignment dimension. The mapping changed, so the identity of
# the extraction changed with it — earlier versions' profiles stay valid and untouched.
ADAPTER_VERSION = "3"

CAPABILITIES = frozenset(
    {
        "course_descriptor",
        "lesson_inventory",
        "lesson_bodies",
        "lesson_assessment_items",
        "assessment_offerings",
        "learning_objectives",
        "declared_objectives",
        "lesson_concepts",
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

# The fence that proposes an exercise, and what the offering it produces is called. The kind
# names the task; the status names its stage. They are orthogonal on purpose — another format
# could deliver a code challenge ready to take.
_PROPOSAL_FENCE = "code_challenge_proposal"
PROPOSED_KIND = "codeChallenge"
DELIVERED = "delivered"
PROPOSED = "proposed"

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


def _proposed_exercises(body: str) -> list[str]:
    """The exercises a lesson PROPOSES, each one the text of its own fence.

    A proposal fence holds the instruction itself — it is what a later step turns into an
    exercise — so unlike the `question` and `fill_in_the_blank` fences, whose bodies hold the
    author's expected answers, what is reported here is the fence's content and not the prose
    around it.

    Fences are tracked the same way `_assessment_items` tracks them, so a proposal fence shown
    INSIDE another fence (a lesson teaching the format, say) is text like any other. A fence
    left unclosed at the end of a body still reports what it holds: the body is what was
    delivered, and half a proposal is what a truncated run produced.
    """
    proposals: list[str] = []
    collecting: list[str] | None = None
    inside_fence = False

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if inside_fence:
                if collecting is not None:
                    proposals.append("\n".join(collecting).strip())
                    collecting = None
                inside_fence = False
                continue
            inside_fence = True
            if stripped[3:].split(" ")[0].strip() == _PROPOSAL_FENCE:
                collecting = []
            continue
        if collecting is not None:
            collecting.append(line)
    if collecting is not None:
        proposals.append("\n".join(collecting).strip())
    return [proposal for proposal in proposals if proposal]


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
            self._assessment_offerings(texts_by_slug, inventory),
            self._learning_objectives(package, fetcher),
            self._declared_objectives(package, fetcher),
            self._lesson_concepts(package, fetcher),
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

    def _assessment_offerings(
        self, texts_by_slug: dict[str, str], inventory: ProfileEntry
    ) -> ProfileEntry:
        """Everything the package offers to assess with, each entry saying which it is.

        Per lesson, what it delivers and then what it proposes — the delivered half is the
        same reading `lesson_assessment_items` reports, not a second interpretation of it, so
        the two ids can never disagree about a question.

        Only the five fields the requirement declares: a delivered item's options live under
        `lesson_assessment_items`, where the id that carries them means one thing for every
        entry, and a proposal has none to report.
        """
        id_by_slug = self._id_by_slug(inventory)
        value: list[dict[str, Any]] = []
        for slug in sorted(texts_by_slug):
            body = texts_by_slug[slug]
            value.extend(
                {
                    "lessonSlug": slug,
                    "lessonId": id_by_slug.get(slug),
                    "status": DELIVERED,
                    "kind": item["kind"],
                    "prompt": item["prompt"],
                }
                for item in _assessment_items(body)
            )
            value.extend(
                {
                    "lessonSlug": slug,
                    "lessonId": id_by_slug.get(slug),
                    "status": PROPOSED,
                    "kind": PROPOSED_KIND,
                    "prompt": proposal,
                }
                for proposal in _proposed_exercises(body)
            )
        if not value:
            # Neither delivered nor proposed: the same statement, for the same reason.
            return ProfileEntry(data_requirement_id="assessment_offerings", provenance="absent")
        return ProfileEntry(
            data_requirement_id="assessment_offerings",
            provenance="declared_in_content",
            value=value,
            quote=_quote(value),
            locator={"source": "artifacts", "kinds": [KIND_LESSON_CONTENT]},
        )

    # --- what the run declares about the commission it served ---------------------------

    def _declared_objectives(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> ProfileEntry:
        """The same objectives `learning_objectives` carries as bare statements, with the
        identity each declares for itself and the criterion it declares would verify it.
        Both ids are supplied on purpose: one is consumed by criteria that count objectives,
        the other by criteria that hold the assessment to what the objective promised."""
        artifact = self._single_artifact(package, KIND_COURSE_VALUE)
        if artifact is None:
            return ProfileEntry(data_requirement_id="declared_objectives", provenance="absent")

        declared = self._json_object(artifact, fetcher).get("learning_objectives")
        objectives = [
            {
                "id": objective["id"],
                "outcome": objective["outcome"],
                # Declared or not: null says the objective is there and its verification is
                # not, which is a different statement from the objective being absent.
                "verifiableBy": (
                    objective["verifiable_by"]
                    if isinstance(objective.get("verifiable_by"), str)
                    else None
                ),
            }
            for objective in declared or []
            if isinstance(objective, dict)
            and isinstance(objective.get("id"), str)
            and isinstance(objective.get("outcome"), str)
        ]
        if not objectives:
            return ProfileEntry(data_requirement_id="declared_objectives", provenance="absent")
        return ProfileEntry(
            data_requirement_id="declared_objectives",
            provenance="declared_structured",
            value=objectives,
            quote=_quote(objectives),
            locator={
                "source": "artifact",
                "kind": KIND_COURSE_VALUE,
                "locator": artifact.locator,
                "path": "$.learning_objectives[*]",
            },
        )

    def _lesson_concepts(self, package: PackageDTO, fetcher: PackageFetcherPort) -> ProfileEntry:
        """What each lesson declares it covers, in the plan's declared order — the
        trajectory, without reading a single body."""
        artifact = self._single_artifact(package, KIND_LESSON_PLAN)
        if artifact is None:
            return ProfileEntry(data_requirement_id="lesson_concepts", provenance="absent")

        lessons = self._json_object(artifact, fetcher).get("lessons")
        concepts = [
            {
                "lessonId": lesson["id"],
                "concept": (
                    lesson["concept_covered"]
                    if isinstance(lesson.get("concept_covered"), str)
                    else None
                ),
            }
            for lesson in lessons or []
            if isinstance(lesson, dict) and isinstance(lesson.get("id"), str)
        ]
        if not concepts:
            return ProfileEntry(data_requirement_id="lesson_concepts", provenance="absent")
        return ProfileEntry(
            data_requirement_id="lesson_concepts",
            provenance="declared_structured",
            value=concepts,
            quote=_quote(concepts),
            locator={
                "source": "artifact",
                "kind": KIND_LESSON_PLAN,
                "locator": artifact.locator,
                "path": "$.lessons[*].concept_covered",
            },
        )

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
