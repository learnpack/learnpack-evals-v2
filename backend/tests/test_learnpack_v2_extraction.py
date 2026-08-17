"""LearnpackV2's extraction convention, beyond what the format contract kit asserts for
every format: the component syntax this format uses, what it refuses to count as assessment,
and the two capabilities LearnpackV1 cannot supply. Against the frozen real package.
No DB, no network."""

import json

import pytest

from app.modules.content_profiling.application.dtos import ArtifactDTO, PackageDTO
from app.modules.content_profiling.domain.profile import ExtractionError
from app.modules.content_profiling.infrastructure.adapters.learnpack_v2 import (
    LearnpackV2Adapter,
    _assessment_items,
    _proposed_exercises,
)
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    LearnpackV2Discovery,
)
from app.shared.domain.ids import new_id
from tests.format_cases import FORMAT_CASES

CASE = FORMAT_CASES["LearnpackV2"]


def extract_fixture():
    """The seam wired the way production wires it: discovery mints the artifacts, the
    adapter reads exactly those."""
    discovered = LearnpackV2Discovery().discover(FilesystemPackageRoot(CASE.fixture_dir))
    package = PackageDTO(
        content_id=new_id(),
        package_format=CASE.package_format,
        artifacts=tuple(
            ArtifactDTO(kind=a.kind, locator=a.locator, format=a.format)
            for a in discovered.artifacts
        ),
    )
    entries, _ = LearnpackV2Adapter().extract(package, FilesystemPackageFetcher(CASE.fixture_dir))
    return {entry.data_requirement_id: entry for entry in entries}


def kinds(body: str) -> list[str]:
    return [item["kind"] for item in _assessment_items(body)]


# ------------------------------------------------------------------ the quiz convention


QUIZ = """Now check your understanding: which part holds the visible content?

1. Which part of an HTML document contains everything the user sees?

    - [ ] <!DOCTYPE html>
    - [x] <body>
    - [ ] <head>
"""


def test_a_quiz_is_an_indented_task_list():
    """This format renders quizzes from a task list indented under its question, where
    LearnpackV1 anchors them at column 0. Both are valid; a reader that assumes one
    convention silently reports a course with no assessment at all."""
    items = _assessment_items(QUIZ)

    assert items == [
        {
            "kind": "multipleChoice",
            "prompt": "Which part of an HTML document contains everything the user sees?",
            "options": ["<!DOCTYPE html>", "<body>", "<head>"],
            "correctCount": 1,
        }
    ]


def test_one_quiz_block_can_hold_several_questions():
    """Why the counts cannot come from `processing_stats`: the stats count COMPONENTS and
    this is one, while an assessment item is one QUESTION and this is two."""
    items = _assessment_items(
        "1. Which CSS property changes text color?\n"
        "\n"
        "    - [ ] text-color\n"
        "    - [x] color\n"
        "2. Which is a valid hex code for white?\n"
        "\n"
        "    - [x] #ffffff\n"
        "    - [ ] #000000\n"
    )

    assert [item["prompt"] for item in items] == [
        "Which CSS property changes text color?",
        "Which is a valid hex code for white?",
    ]
    assert [item["correctCount"] for item in items] == [1, 1]


def test_a_bulleted_question_carries_the_prompt_too():
    """The component's spec allows the question to be numbered or bulleted."""
    items = _assessment_items("- Which tag holds the page title?\n\n    - [x] <title>\n")

    assert items[0]["prompt"] == "Which tag holds the page title?"


def test_options_outside_the_rendered_indent_are_not_a_quiz():
    """3-6 spaces is the format's contract with the markdown renderer. A task list outside
    it does not render as a quiz, so the learner never sees one — counting it would credit
    the course with assessment nobody can take."""
    assert kinds("1. A question?\n\n- [x] flush left\n") == []
    assert kinds("1. A question?\n\n        - [x] eight spaces\n") == []


def test_a_group_with_two_correct_options_reports_what_it_marks():
    """The component's spec asks for a unique correct answer, but enforcing that is a
    criterion's job. The adapter reports; it does not judge (ADR-0009)."""
    items = _assessment_items("1. Pick one\n\n    - [x] first\n    - [x] second\n")

    assert len(items) == 1
    assert items[0]["correctCount"] == 2


# ------------------------------------------------------------------ what is not assessment


@pytest.mark.parametrize(
    ("label", "body"),
    [
        (
            "code challenge proposal",
            "Now open index.html.\n\n```code_challenge_proposal\nWrite an img tag.\n```\n",
        ),
        ("mermaid diagram", "The skeleton:\n\n```mermaid\ngraph TD\n  A --> B\n```\n"),
        ("illustration prompt", "![A flat illustration of a blueprint](./.learn/assets/x.png)\n"),
        (
            "rigo link",
            "[Ask Rigo about HTML attributes](https://4geeks.com/ask?query=what-is-html)\n",
        ),
    ],
)
def test_author_facing_components_are_not_delivered_assessment_items(label, body):
    """A proposal is the prompt a teacher will later turn into an exercise, and the
    illustration's alt text is a prompt for generating an image. Neither is something a
    learner can answer as it stands, so neither is a DELIVERED item.

    The proposal is the one of the four that is evidence of something (ADR-0046): it travels
    in `assessment_offerings` marked `proposed`, and it must never leak into this id, where
    every entry means "ready for the learner"."""
    assert kinds(body) == []


def test_a_quiz_inside_a_fence_is_not_counted():
    assert kinds("```html\n1. Not a question\n\n    - [x] not an option\n```\n") == []


def test_the_fenced_components_take_their_prompt_from_the_prose():
    """The fence body holds the author's expected answers, not the question — the same rule
    LearnpackV1 follows."""
    items = _assessment_items(
        "Identify the purpose of the head section.\n\n"
        '```question eval="mentions metadata"\nCORRECT: metadata\n```\n'
    )

    assert items == [
        {
            "kind": "openQuestion",
            "prompt": "Identify the purpose of the head section.",
            "options": [],
            "correctCount": 0,
        }
    ]


# --------------------------------------------------------------- what the package proposes


PROPOSAL = """Now it's your turn. Open `index.html` and write an `<img>` tag.

```code_challenge_proposal
In this exercise, the student needs to write an <img> tag in index.html that
displays a placeholder image from https://picsum.photos/200/300.
```

If you get stuck, Rigo can help.
"""


def test_a_proposal_reports_the_fence_s_own_text():
    """The asymmetry with `question`, and the format's: inside a `question` fence the author
    writes the expected answers, so its prompt is the prose before it — while a proposal fence
    holds the instruction itself, and quoting the prose around it would report the lead-in
    instead of what was proposed."""
    assert _proposed_exercises(PROPOSAL) == [
        "In this exercise, the student needs to write an <img> tag in index.html that\n"
        "displays a placeholder image from https://picsum.photos/200/300."
    ]


def test_every_proposal_of_a_lesson_is_reported():
    body = (
        "```code_challenge_proposal\nBuild a nav.\n```\n"
        "Some prose in between.\n"
        "```code_challenge_proposal\nStyle it.\n```\n"
    )

    assert _proposed_exercises(body) == ["Build a nav.", "Style it."]


def test_a_proposal_shown_inside_another_fence_is_text_like_any_other():
    """A lesson that teaches this very format would otherwise be read as proposing an
    exercise it is only quoting."""
    assert _proposed_exercises("```markdown\n```code_challenge_proposal\nNot mine.\n```\n") == []


def test_an_unclosed_proposal_reports_what_it_holds():
    """The body is what was delivered: half a proposal is what a truncated run produced, and
    reporting nothing would hide it."""
    assert _proposed_exercises("```code_challenge_proposal\nBuild a nav bar with\n") == [
        "Build a nav bar with"
    ]


def test_the_offerings_carry_both_kinds_marked():
    """ADR-0046: one id for everything the package offers to assess with, so a criterion
    asking what the draft commits to measuring sees the whole surface — and can still tell
    the two apart, because the mark is on every entry."""
    offerings = extract_fixture()["assessment_offerings"].value
    statuses = {offering["status"] for offering in offerings}

    assert statuses == {"delivered", "proposed"}
    proposed = [o for o in offerings if o["status"] == "proposed"]
    assert len(proposed) == 5
    assert {o["kind"] for o in proposed} == {"codeChallenge"}
    assert all(o["lessonId"] and o["prompt"].strip() for o in proposed)


def test_the_delivered_offerings_are_the_assessment_items_verbatim():
    """The two ids report one reading, not two: whatever `lesson_assessment_items` says a
    lesson delivers is what the offerings mark `delivered`. Nothing downstream could tell
    which id a quote came from, and nothing should have to."""
    entries = extract_fixture()
    delivered = [o for o in entries["assessment_offerings"].value if o["status"] == "delivered"]

    assert [(o["lessonId"], o["kind"], o["prompt"]) for o in delivered] == [
        (item["lessonId"], item["kind"], item["prompt"])
        for item in entries["lesson_assessment_items"].value
    ]


def test_the_offerings_declare_only_the_five_fields_the_requirement_names():
    """A delivered item's options live under `lesson_assessment_items`, where every entry
    means the same thing. Carrying them here would leave a proposal describing options it
    does not have."""
    offerings = extract_fixture()["assessment_offerings"].value

    assert {key for offering in offerings for key in offering} == {
        "lessonSlug",
        "lessonId",
        "status",
        "kind",
        "prompt",
    }


# ------------------------------------------------------------------ over the real package


def test_the_descriptor_reports_only_what_the_run_declares():
    """A run declares no course description and no technologies — the teacher writes those
    downstream — and this fixture was commissioned without a difficulty."""
    assert extract_fixture()["course_descriptor"].value == {
        "slug": "03-html-fundamentals",
        "title": "HTML Fundamentals: Building Web Page Structure",
        "description": None,
        "technologies": [],
        "difficulty": None,
    }


def test_the_inventory_names_each_lesson_through_the_run_stats():
    """The plan lists ids and never a filename; the stats are what tie an id to its file."""
    inventory = extract_fixture()["lesson_inventory"]

    assert len(inventory.value) == 11
    assert inventory.value[0] == {
        "lessonId": "00.0",
        "slug": "00.0-welcome-to-html-fundamentals",
        "position": 0,
        "type": "READ",
        "title": "Welcome to HTML Fundamentals",
    }
    assert [lesson["position"] for lesson in inventory.value] == list(range(11))


def test_the_two_capabilities_learnpack_v1_cannot_supply():
    """What this format declares as structured fields, and V1 declares nowhere — the reason
    three criteria stop deriving `not_applicable`."""
    entries = extract_fixture()

    objectives = entries["learning_objectives"]
    assert len(objectives.value) == 3
    assert all(isinstance(outcome, str) for outcome in objectives.value)
    assert objectives.value[0].startswith("The learner can identify the structure")
    assert entries["target_audience"].value == (
        "Complete beginners with no prior web development experience"
    )


def test_the_bodies_are_kept_verbatim():
    entries = extract_fixture()
    body = next(
        entry["body"]
        for entry in entries["lesson_bodies"].value
        if entry["lessonSlug"] == "00.0-welcome-to-html-fundamentals"
    )

    # Bytes, not text mode: verbatim means the line endings too, and a universal-newline
    # read would quietly agree on Windows about something the adapter never did.
    on_disk = (CASE.fixture_dir / "lessons" / "00.0-welcome-to-html-fundamentals.md").read_bytes()
    assert body == on_disk.decode("utf-8")


def test_what_the_body_delivers_matches_what_the_run_recorded():
    """A bounded canary, not a source of truth. Restricted to the fenced components: the
    stats count quiz COMPONENTS while the adapter counts questions, and a component the
    generator failed to emit is recorded with `resolved: false` and legitimately absent
    from the body. Where the two ever disagree beyond that, the body is what was delivered.
    """
    fenced = {"open_text_question": "openQuestion", "fill_in_the_blank": "fillInTheBlank"}
    items = extract_fixture()["lesson_assessment_items"].value

    for stats_file in sorted((CASE.fixture_dir / "files" / "processing_stats").glob("*.json")):
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
        unresolved = {r["type"] for r in stats["component_retries"] if not r.get("resolved")}
        for declared_kind, item_kind in fenced.items():
            if declared_kind in unresolved:
                continue
            observed = [
                i
                for i in items
                if i["lessonSlug"] == stats["lesson_slug"] and i["kind"] == item_kind
            ]
            assert len(observed) == stats["component_type_counts"].get(declared_kind, 0), (
                f"{stats['lesson_slug']}: {declared_kind}"
            )


# ------------------------------------------------------------------ absence and failure


class DictFetcher:
    def __init__(self, files: dict[str, bytes]) -> None:
        self._files = files

    def fetch(self, locator: str) -> bytes:
        if locator not in self._files:
            raise ExtractionError(f"unreachable: {locator}")
        return self._files[locator]


def _package(**files: bytes) -> tuple[PackageDTO, DictFetcher]:
    kinds_by_name = {
        "run_metadata.json": "run_manifest",
        "lesson_plan.json": "lesson_plan",
        "course_value.json": "course_value",
        "user_intent.json": "user_intent",
        "stats.json": "lesson_stats",
        "a-lesson.md": "lesson_content",
    }
    package = PackageDTO(
        content_id=new_id(),
        package_format="LearnpackV2",
        artifacts=tuple(
            ArtifactDTO(kind=kinds_by_name[name], locator=name, format=None) for name in files
        ),
    )
    return package, DictFetcher(dict(files))


def test_a_course_with_no_assessment_reports_absence_not_an_empty_list():
    """ADR-0009: an empty list would read as 'assessment exists and is empty', which would
    let a course with none of it pass a criterion instead of failing to evidence one."""
    package, fetcher = _package(
        **{
            "run_metadata.json": b'{"system_metadata": {"run_info": {"seed_id": "s"}}}',
            "lesson_plan.json": b'{"course_title": "T", "lessons": [{"id": "00.0"}]}',
            "stats.json": b'{"lesson_id": "00.0", "lesson_slug": "a-lesson"}',
            "a-lesson.md": b"# A lesson\n\nProse only, nothing to answer.\n",
        }
    )

    entries = {e.data_requirement_id: e for e in LearnpackV2Adapter().extract(package, fetcher)[0]}

    assert entries["lesson_assessment_items"].provenance == "absent"
    assert entries["lesson_assessment_items"].value is None
    # Nothing delivered and nothing proposed is the same statement, for the same reason.
    assert entries["assessment_offerings"].provenance == "absent"
    assert entries["assessment_offerings"].value is None
    assert entries["lesson_bodies"].provenance == "declared_in_content"


def test_a_course_that_delivers_nothing_but_proposes_something_still_offers_assessment():
    """The shape ADR-0046 was decided for, and the reason the two are one id: three of the
    five drafts on hand are a single question block away from this, and under two ids every
    alignment criterion would go silent on a draft holding exactly the evidence they ask
    for."""
    package, fetcher = _package(
        **{
            "lesson_plan.json": b'{"course_title": "T", "lessons": [{"id": "00.0"}]}',
            "stats.json": b'{"lesson_id": "00.0", "lesson_slug": "a-lesson"}',
            "a-lesson.md": (b"# A lesson\n\n```code_challenge_proposal\nBuild a nav bar.\n```\n"),
        }
    )

    entries = {e.data_requirement_id: e for e in LearnpackV2Adapter().extract(package, fetcher)[0]}

    assert entries["lesson_assessment_items"].provenance == "absent"
    assert entries["assessment_offerings"].value == [
        {
            "lessonSlug": "a-lesson",
            "lessonId": "00.0",
            "status": "proposed",
            "kind": "codeChallenge",
            "prompt": "Build a nav bar.",
        }
    ]


def test_a_commission_that_declared_no_audience_reports_absence():
    """`user_intent` states what it was not told — `missing_fields` lists it — and an absent
    entry is that same statement in the profile's vocabulary."""
    package, fetcher = _package(
        **{
            "user_intent.json": b'{"target_audience": null, "missing_fields": ["target_audience"]}',
        }
    )

    entries = {e.data_requirement_id: e for e in LearnpackV2Adapter().extract(package, fetcher)[0]}

    assert entries["target_audience"].provenance == "absent"


def test_an_unparseable_artifact_fails_the_whole_extraction():
    package, fetcher = _package(
        **{
            "run_metadata.json": b"{not json",
            "lesson_plan.json": b'{"lessons": []}',
        }
    )

    with pytest.raises(ExtractionError, match="not valid JSON"):
        LearnpackV2Adapter().extract(package, fetcher)


# ------------------------------------------------------------------ the alignment data


def test_the_objectives_travel_with_their_declared_verification():
    """What `learning_objectives` cannot carry: the id each objective declares for itself and
    the criterion it says would verify it. The second is what lets a criterion hold the
    assessment to the objective's own promise instead of to ours."""
    objectives = extract_fixture()["declared_objectives"].value

    assert len(objectives) == 3
    assert objectives[0]["id"] == "obj-1"
    assert objectives[0]["outcome"].startswith("The learner can identify the structure")
    assert objectives[0]["verifiableBy"].startswith("Given a labeled diagram")


def test_the_two_objective_ids_carry_the_same_objectives():
    """Both are supplied on purpose and must not drift: one counts them, the other compares
    against them, and a course where they disagreed would be judged twice over."""
    entries = extract_fixture()

    assert [o["outcome"] for o in entries["declared_objectives"].value] == (
        entries["learning_objectives"].value
    )


def test_an_objective_without_a_declared_verification_reports_null():
    """Present-and-null, never omitted: the objective is there and its verification is not,
    which is a different statement from the objective being absent (ADR-0020)."""
    package, fetcher = _package(
        **{
            "course_value.json": (
                b'{"learning_objectives": [{"id": "obj-1", "outcome": "Do a thing"}]}'
            ),
        }
    )

    entries = {e.data_requirement_id: e for e in LearnpackV2Adapter().extract(package, fetcher)[0]}

    assert entries["declared_objectives"].value == [
        {"id": "obj-1", "outcome": "Do a thing", "verifiableBy": None}
    ]


def test_the_lesson_concepts_follow_the_plan_s_declared_order():
    """The trajectory, read without opening a single body."""
    concepts = extract_fixture()["lesson_concept_coverage"].value
    inventory = extract_fixture()["lesson_inventory"].value

    assert [c["lessonId"] for c in concepts] == [lesson["lessonId"] for lesson in inventory]
    assert concepts[0] == {"lessonId": "00.0", "concepts": ["welcome"]}
    assert concepts[1]["concepts"] == ["HTML as markup language"]


def test_a_lesson_can_declare_several_concepts():
    """The format's own set, carried whole — the trajectory does not collapse it to one."""
    concepts = extract_fixture()["lesson_concept_coverage"].value

    by_id = {c["lessonId"]: c["concepts"] for c in concepts}
    assert by_id["02.0"] == ["HTML element syntax", "Tags"]


def test_the_framing_lessons_declare_their_own_concepts():
    """`welcome` and `course-outro` are named concepts like any other, and they sit outside
    the course's concept graph by convention. The adapter reports what the plan declares and
    leaves that distinction to the criteria that care about it."""
    concepts = extract_fixture()["lesson_concept_coverage"].value

    assert concepts[0]["concepts"] == ["welcome"]
    assert concepts[-1]["concepts"] == ["course-outro"]


def test_a_lesson_that_names_no_concept_reports_an_empty_list():
    package, fetcher = _package(
        **{
            "lesson_plan.json": (
                b'{"lessons": [{"id": "00.0"}, {"id": "01.0", "concepts_covered": ["x"]}]}'
            ),
        }
    )

    entries = {e.data_requirement_id: e for e in LearnpackV2Adapter().extract(package, fetcher)[0]}

    assert entries["lesson_concept_coverage"].value == [
        {"lessonId": "00.0", "concepts": []},
        {"lessonId": "01.0", "concepts": ["x"]},
    ]
