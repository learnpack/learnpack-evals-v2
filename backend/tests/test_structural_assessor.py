"""`structural` v1 — executors over synthetic profiles + coverage vs the real YAML.

Criterion specs are built from the shipped instrument, so the by-position failure-mode
selection is exercised against the team's actual wording; the disjoint-union test pins
instrument<->assessor coverage drift in CI without a DB.
"""

from uuid import uuid4

import yaml

from app.modules.evaluation.domain.model import (
    CriterionSpec,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS, structural
from tests.conftest import INSTRUMENT_SPEC_FILE

PACKAGE = AUTOMATED_ASSESSORS[("structural", "1")]

_REAL_SPEC = yaml.safe_load(INSTRUMENT_SPEC_FILE.read_text(encoding="utf-8"))
_REAL_CRITERIA = {
    raw["id"]: CriterionSpec(
        criterion_id=raw["id"],
        pass_condition=raw["pass_condition"],
        failure_modes=tuple(raw["failure_modes"]),
        claim_ids=tuple(raw["claims"]),
        required_data=tuple(raw["requires"]),
        on_missing_evidence=raw.get("on_missing_evidence", "no_evidence"),
    )
    for raw in _REAL_SPEC["criteria"]
}


def entry(datum: str, value) -> ProfileEntryData:
    return ProfileEntryData(
        data_requirement_id=datum,
        provenance="declared_structured",
        value=value,
        quote=f"canonical serialization of {datum}",
        locator={"artifact": "package_manifest"},
    )


def profile(**values) -> ProfileData:
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV1",
        entries={datum: entry(datum, value) for datum, value in values.items()},
    )


def lesson(lesson_id: str, position: int, slug: str | None = None) -> dict:
    return {
        "lessonId": lesson_id,
        "slug": slug or f"lesson-{lesson_id}",
        "position": position,
        "type": "lesson",
        "title": f"Lesson {lesson_id}",
    }


def activities(slug: str, count: int = 0, exercises: list[str] | None = None) -> dict:
    return {
        "lessonSlug": slug,
        "lessonId": None,
        "activities": {
            "multipleChoice": count,
            "openQuestion": 0,
            "selectTheBlank": 0,
            "ordering": 0,
            "fillInTheBlank": 0,
        },
        "codeExercises": exercises or [],
    }


WELL_FORMED = [
    lesson("00.0", 0),
    lesson("01.0", 1),
    lesson("01.1", 2),
    lesson("02.0", 3),
    lesson("02.1", 4),
]


# --- coverage vs the shipped instrument ----------------------------------------------


def test_coverage_is_a_disjoint_union_over_the_real_criteria():
    declared = {raw["id"] for raw in _REAL_SPEC["criteria"]}
    assert PACKAGE.coverage.declared == declared
    assert not (PACKAGE.coverage.executes & set(PACKAGE.coverage.abstains))
    assert PACKAGE.instrument_id == _REAL_SPEC["instrument_id"]


def test_every_executed_failure_index_exists_in_the_real_instrument():
    # Executors select modes by position 0/1; every executed criterion declares >= 1.
    for criterion_id in PACKAGE.coverage.executes:
        assert len(_REAL_CRITERIA[criterion_id].failure_modes) >= 1


# --- declaration executors ------------------------------------------------------------


def test_objectives_min_count():
    spec = _REAL_CRITERIA["cr-objectives-min-count"]
    run = structural.EXECUTORS["cr-objectives-min-count"]

    passing = run(spec, profile(learning_objectives=["build an API", "write tests"]))
    assert passing.passed and passing.quote

    none_declared = run(spec, profile(learning_objectives=["  "]))
    assert not none_declared.passed
    assert none_declared.failure_mode == spec.failure_modes[0]

    catch_all = run(spec, profile(learning_objectives=["learn everything about Python"]))
    assert catch_all.failure_mode == spec.failure_modes[1]


def test_audience_declared():
    spec = _REAL_CRITERIA["cr-audience-declared"]
    run = structural.EXECUTORS["cr-audience-declared"]

    assert run(spec, profile(target_audience="junior devs with basic JS")).passed
    assert run(spec, profile(target_audience="  ")).failure_mode == spec.failure_modes[0]
    assert run(spec, profile(target_audience="Everyone.")).failure_mode == spec.failure_modes[1]


def test_prerequisites_declared():
    spec = _REAL_CRITERIA["cr-prerequisites-declared"]
    run = structural.EXECUTORS["cr-prerequisites-declared"]

    assert run(spec, profile(prerequisites=["basic HTML"])).passed
    assert run(spec, profile(prerequisites=["none"])).passed  # declaring the empty set
    assert not run(spec, profile(prerequisites=["  "])).passed


# --- structural executors -------------------------------------------------------------


def test_lessons_with_activities_ratio():
    spec = _REAL_CRITERIA["cr-lessons-with-activities"]
    run = structural.EXECUTORS["cr-lessons-with-activities"]
    # Core lessons = 01.0, 01.1, 02.0 (00.0 is the intro, 02.1 the closing slot).
    base = dict(lesson_inventory=WELL_FORMED)

    covered = run(
        spec,
        profile(
            **base,
            lesson_activities=[
                activities("lesson-01.0", count=2),
                activities("lesson-01.1", exercises=["app.py"]),
                activities("lesson-02.0"),
            ],
        ),
    )
    assert covered.passed
    metrics = {m.metric_id: m.value for m in covered.metrics}
    assert metrics["core_lessons"] == 3
    assert metrics["core_lessons_with_activities"] == 2

    expository = run(spec, profile(**base, lesson_activities=[activities("lesson-01.0")]))
    assert expository.failure_mode == spec.failure_modes[0]

    concentrated = run(
        spec,
        profile(**base, lesson_activities=[activities("lesson-01.0", count=5)]),
    )
    assert concentrated.failure_mode == spec.failure_modes[1]


def test_module_structure_well_formed():
    spec = _REAL_CRITERIA["cr-module-structure-well-formed"]
    run = structural.EXECUTORS["cr-module-structure-well-formed"]

    assert run(spec, profile(lesson_inventory=WELL_FORMED)).passed

    drift = run(spec, profile(lesson_inventory=[lesson("00.0", 0), lesson("05", 1)]))
    assert drift.failure_mode == spec.failure_modes[0]

    gap = run(
        spec,
        profile(lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1), lesson("03.0", 2)]),
    )
    assert gap.failure_mode == spec.failure_modes[1]

    late_start = run(spec, profile(lesson_inventory=[lesson("00.0", 0), lesson("01.1", 1)]))
    assert late_start.failure_mode == spec.failure_modes[0]  # lesson numbering not at .0


def test_course_opens_with_general_intro():
    spec = _REAL_CRITERIA["cr-course-opens-with-general-intro"]
    run = structural.EXECUTORS["cr-course-opens-with-general-intro"]

    assert run(spec, profile(lesson_inventory=WELL_FORMED)).passed
    assert not run(spec, profile(lesson_inventory=[lesson("01.0", 0)])).passed
    two_intros = [lesson("00.0", 0), lesson("00.1", 1), lesson("01.0", 2)]
    assert not run(spec, profile(lesson_inventory=two_intros)).passed


def test_course_has_development():
    spec = _REAL_CRITERIA["cr-course-has-development"]
    run = structural.EXECUTORS["cr-course-has-development"]

    assert run(spec, profile(lesson_inventory=WELL_FORMED)).passed
    stub = run(spec, profile(lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1)]))
    assert not stub.passed
    # No module 00: the first lesson is the opening slot.
    no_intro = run(
        spec,
        profile(lesson_inventory=[lesson("01.0", 0), lesson("01.1", 1), lesson("02.0", 2)]),
    )
    assert no_intro.passed


# --- type/delivery correspondence and the lexical-load measure ------------------------


def coded(lesson_id: str, position: int, slug: str | None = None) -> dict:
    """A lesson the manifest declares as practice."""
    return {**lesson(lesson_id, position, slug), "type": "CODE"}


def test_lesson_type_matches_delivery_reads_both_directions():
    spec = _REAL_CRITERIA["cr-lesson-type-matches-delivery"]
    run = structural.EXECUTORS["cr-lesson-type-matches-delivery"]

    # Declared and delivered agree.
    ok = run(
        spec,
        profile(
            lesson_inventory=[lesson("01.0", 0), coded("01.1", 1)],
            lesson_activities=[
                activities("lesson-01.0"),
                activities("lesson-01.1", exercises=["index.html"]),
            ],
        ),
    )
    assert ok.passed

    # Declared practice that ships nothing: the learner meets an empty editor.
    promised = run(
        spec,
        profile(
            lesson_inventory=[lesson("01.0", 0), coded("01.1", 1)],
            lesson_activities=[activities("lesson-01.0"), activities("lesson-01.1")],
        ),
    )
    assert not promised.passed
    assert "empty editor" in promised.failure_mode

    # The inverse the corpus also holds: an exercise in a lesson not declared as practice.
    undeclared = run(
        spec,
        profile(
            lesson_inventory=[lesson("01.0", 0), lesson("01.1", 1)],
            lesson_activities=[
                activities("lesson-01.0"),
                activities("lesson-01.1", exercises=["app.py"]),
            ],
        ),
    )
    assert not undeclared.passed
    assert "not declared as practice" in undeclared.failure_mode

    # A course that neither declares nor ships code practice satisfies the correspondence.
    silent = run(
        spec,
        profile(
            lesson_inventory=[lesson("01.0", 0), lesson("01.1", 1)],
            lesson_activities=[activities("lesson-01.0"), activities("lesson-01.1")],
        ),
    )
    assert silent.passed


def body(slug: str, text: str) -> dict:
    return {"lessonSlug": slug, "lessonId": None, "body": text}


def test_no_lesson_spikes_in_lexical_load():
    spec = _REAL_CRITERIA["cr-no-lesson-spikes-in-lexical-load"]
    run = structural.EXECUTORS["cr-no-lesson-spikes-in-lexical-load"]

    plain = " ".join(["the cat sat on a mat and the dog ran to the big red bus"] * 12)
    dense = " ".join(
        ["extraordinarily sophisticated methodological considerations demonstrate"] * 22
    )

    even = run(spec, profile(lesson_bodies=[body("a", plain), body("b", plain), body("c", plain)]))
    assert even.passed

    spiked = run(
        spec, profile(lesson_bodies=[body("a", plain), body("b", plain), body("c", dense)])
    )
    assert not spiked.passed
    metrics = {m.metric_id: m.value for m in spiked.metrics}
    assert metrics["lexical_load_spikes"] == ["c"]
    assert metrics["lessons_measured"] == 3


def test_short_lessons_neither_set_nor_break_the_median():
    """Below the guard the mean is dominated by whichever few words a lesson used."""
    spec = _REAL_CRITERIA["cr-no-lesson-spikes-in-lexical-load"]
    run = structural.EXECUTORS["cr-no-lesson-spikes-in-lexical-load"]

    plain = " ".join(["the cat sat on a mat and the dog ran to the big red bus"] * 12)
    result = run(
        spec,
        profile(lesson_bodies=[body("a", plain), body("tiny", "Extraordinarily sophisticated.")]),
    )
    assert result.passed
    assert {m.metric_id: m.value for m in result.metrics}["lessons_measured"] == 1


def test_a_course_of_only_short_lessons_has_nothing_to_compare():
    spec = _REAL_CRITERIA["cr-no-lesson-spikes-in-lexical-load"]
    run = structural.EXECUTORS["cr-no-lesson-spikes-in-lexical-load"]

    result = run(spec, profile(lesson_bodies=[body("a", "Too short."), body("b", "Also short.")]))
    assert result.passed
    assert {m.metric_id: m.value for m in result.metrics}["lessons_measured"] == 0


def test_code_fences_and_image_alt_text_are_not_prose():
    """A code block is not prose, and LearnPack's generated illustrations carry their whole
    image-generation prompt as alt text — counting either would measure the wrong thing."""
    from app.modules.evaluation.infrastructure.assessors.structural import measures

    prose = " ".join(["the cat sat on a mat and the dog ran to the big red bus"] * 12)
    noisy = (
        prose
        + "\n\n```python\nextraordinarily_sophisticated_methodological_consideration = 1\n```\n"
        + "\n![GENERATING: extraordinarily sophisticated methodological illustration](/x.png)\n"
    )
    assert measures.lexical_load(noisy) == measures.lexical_load(prose)
