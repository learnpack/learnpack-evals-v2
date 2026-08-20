"""`drafts-structural` v1 — coverage vs the real drafts YAML, the copied executors, the
ratification act, and the whole package against the frozen LearnpackV2 fixture.

Criterion specs are built from the shipped instrument, so the by-position failure-mode
selection is exercised against the team's actual wording; the disjoint-union test pins
instrument<->assessor coverage drift in CI without a DB. The executors' algorithms are
already pinned by `test_structural_assessor.py` — the copies get one pass + one fail each,
which proves the wiring and the mode selection, not the arithmetic again. The exception is
`objectives_min_count`, whose metric rename is the one deliberate behavioural difference.
"""

import copy
import dataclasses
import statistics
from uuid import uuid4

import pytest
import yaml
from test_automated_evaluation_flow import publish_instrument, track_automated
from test_learnpack_v2_extraction import extract_fixture

from app.cli import run_ratify_assessor
from app.modules.evaluation.domain.derivation import derive_and_execute
from app.modules.evaluation.domain.model import (
    BindingSpec,
    ClaimSpec,
    CriterionSpec,
    InstrumentSpec,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation.infrastructure.assessors.drafts_structural import measures
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from tests.conftest import DRAFTS_INSTRUMENT_SPEC_FILE, INSTRUMENTS_DIR

PACKAGE = AUTOMATED_ASSESSORS[("drafts-structural", "1")]

_REAL_SPEC = yaml.safe_load(DRAFTS_INSTRUMENT_SPEC_FILE.read_text(encoding="utf-8"))
_REAL_CRITERIA = {
    raw["id"]: CriterionSpec(
        criterion_id=raw["id"],
        pass_condition=raw["pass_condition"],
        failure_modes=tuple(raw["failure_modes"]),
        claim_ids=tuple(raw["claims"]),
        required_data=tuple(raw["requires"]),
        on_missing_evidence=raw.get("on_missing_evidence", "no_evidence"),
        condition=raw.get("condition"),
    )
    for raw in _REAL_SPEC["criteria"]
}


def entry(datum: str, value) -> ProfileEntryData:
    return ProfileEntryData(
        data_requirement_id=datum,
        provenance="declared_structured",
        value=value,
        quote=f"canonical serialization of {datum}",
        locator={"artifact": "lesson_plan"},
    )


def profile(**values) -> ProfileData:
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
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


def body(slug: str, text: str) -> dict:
    return {"lessonSlug": slug, "lessonId": None, "body": text}


WELL_FORMED = [
    lesson("00.0", 0),
    lesson("01.0", 1),
    lesson("01.1", 2),
    lesson("02.0", 3),
    lesson("02.1", 4),
]


# --- coverage vs the shipped instrument ----------------------------------------------


def test_coverage_decides_the_shipped_instrument_and_nothing_stray():
    """Every criterion of the version this artifact targets is decided, nothing is decided
    twice, and nothing is decided that no version of the lineage declares.

    A superset of the shipped version rather than an equality with it, since v9 retires an id
    v8 still declares and the artifact has to keep deciding both."""
    shipped = {raw["id"] for raw in _REAL_SPEC["criteria"]}
    assert shipped <= PACKAGE.coverage.declared
    assert not (PACKAGE.coverage.executes & set(PACKAGE.coverage.abstains))
    assert PACKAGE.instrument_id == _REAL_SPEC["instrument_id"]

    lineage: set[str] = set()
    for spec_file in INSTRUMENTS_DIR.glob("course-drafts-qa-v*.yaml"):
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        lineage |= {raw["id"] for raw in spec["criteria"]}
    assert not PACKAGE.coverage.declared - lineage


def test_coverage_decides_every_criterion_of_every_version_of_the_lineage():
    """Ratification demands coverage ⊇ the target version's criteria (ADR-0019), and the
    artifact has to satisfy that for every version anyone might ratify it against.

    Read off disk rather than from a list of version numbers: versions are deleted when
    nothing reads them any more, and a hardcoded list turns that into a failing test about a
    file instead of a claim about coverage. A SUPERSET of each version rather than an equality
    with any one of them, because v9 retires an id v8 still declares — no single version's
    criteria equal what this artifact must decide.
    """
    versions = sorted(INSTRUMENTS_DIR.glob("course-drafts-qa-v*.yaml"))
    assert versions, "the lineage should have at least one version on disk"
    for spec_file in versions:
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        undecided = {raw["id"] for raw in spec["criteria"]} - PACKAGE.coverage.declared
        assert not undecided, f"{spec_file.name}: {', '.join(sorted(undecided))}"


def test_every_executed_failure_index_exists_in_the_real_instrument():
    # Executors select modes by position 0/1; every executed criterion declares >= 1.
    for criterion_id in PACKAGE.coverage.executes:
        assert len(_REAL_CRITERIA[criterion_id].failure_modes) >= 1


def test_the_dropped_structural_executors_are_not_declared():
    """The drafts instrument deliberately dropped the `lesson_activities` criteria; a
    careless full copy of `structural` would declare coverage over ids this lineage
    never defined."""
    assert "cr-lessons-with-activities" not in PACKAGE.coverage.declared
    assert "cr-lesson-type-matches-delivery" not in PACKAGE.coverage.declared


# --- the one deliberate behavioural difference: the renamed metric --------------------


def test_objectives_min_count_metric_is_renamed():
    """This lineage mints a data requirement `declared_objectives` (the objectives, with
    their declared verification), so the COUNT the executor computes carries a name of its
    own — `structural` v1 keeps the old name in its own lineage, where nothing collides."""
    spec = _REAL_CRITERIA["cr-objectives-min-count"]
    run = PACKAGE.executors["cr-objectives-min-count"]

    passing = run(spec, profile(learning_objectives=["build an API", "write tests"]))
    assert passing.passed and passing.quote
    assert {m.metric_id for m in passing.metrics} == {"declared_objectives_count"}
    assert {m.metric_id: m.value for m in passing.metrics}["declared_objectives_count"] == 2

    none_declared = run(spec, profile(learning_objectives=["  "]))
    assert not none_declared.passed
    assert none_declared.failure_mode == spec.failure_modes[0]
    assert {m.metric_id for m in none_declared.metrics} == {"declared_objectives_count"}

    catch_all = run(spec, profile(learning_objectives=["learn everything about HTML"]))
    assert catch_all.failure_mode == spec.failure_modes[1]


# --- the copied executors: one pass + one fail each, against THIS instrument's wording --


def test_audience_declared():
    spec = _REAL_CRITERIA["cr-audience-declared"]
    run = PACKAGE.executors["cr-audience-declared"]

    assert run(spec, profile(target_audience="junior devs with basic JS")).passed
    assert run(spec, profile(target_audience="Everyone.")).failure_mode == spec.failure_modes[1]


def test_prerequisites_declared():
    spec = _REAL_CRITERIA["cr-prerequisites-declared"]
    run = PACKAGE.executors["cr-prerequisites-declared"]

    assert run(spec, profile(prerequisites=["none"])).passed  # declaring the empty set
    assert not run(spec, profile(prerequisites=["  "])).passed


def test_module_structure_well_formed():
    spec = _REAL_CRITERIA["cr-module-structure-well-formed"]
    run = PACKAGE.executors["cr-module-structure-well-formed"]

    assert run(spec, profile(lesson_inventory=WELL_FORMED)).passed
    drift = run(spec, profile(lesson_inventory=[lesson("00.0", 0), lesson("05", 1)]))
    assert drift.failure_mode == spec.failure_modes[0]


def test_course_opens_with_general_intro():
    spec = _REAL_CRITERIA["cr-course-opens-with-general-intro"]
    run = PACKAGE.executors["cr-course-opens-with-general-intro"]

    assert run(spec, profile(lesson_inventory=WELL_FORMED)).passed
    assert not run(spec, profile(lesson_inventory=[lesson("01.0", 0)])).passed


def test_course_has_development():
    spec = _REAL_CRITERIA["cr-course-has-development"]
    run = PACKAGE.executors["cr-course-has-development"]

    assert run(spec, profile(lesson_inventory=WELL_FORMED)).passed
    stub = run(spec, profile(lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1)]))
    assert not stub.passed


def test_no_lesson_spikes_in_lexical_load():
    spec = _REAL_CRITERIA["cr-no-lesson-spikes-in-lexical-load"]
    run = PACKAGE.executors["cr-no-lesson-spikes-in-lexical-load"]

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
    assert {m.metric_id: m.value for m in spiked.metrics}["lexical_load_spikes"] == ["c"]


# --- the whole package against the frozen LearnpackV2 fixture -------------------------


def _fixture_profile() -> ProfileData:
    """The frozen V2 run, extracted the way production extracts it, translated once into
    this module's own types — the same translation the profiling gateway performs."""
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
        entries={
            requirement_id: ProfileEntryData(
                data_requirement_id=requirement_id,
                provenance=extracted.provenance,
                value=extracted.value,
                quote=extracted.quote,
                locator=extracted.locator,
            )
            for requirement_id, extracted in extract_fixture().items()
        },
    )


def _instrument_spec() -> InstrumentSpec:
    return InstrumentSpec(
        instrument_version_id="course-drafts-qa-v8",
        instrument_id=_REAL_SPEC["instrument_id"],
        status="published",
        claims=tuple(ClaimSpec(claim_id=raw["id"]) for raw in _REAL_SPEC["claims"]),
        criteria=tuple(_REAL_CRITERIA[raw["id"]] for raw in _REAL_SPEC["criteria"]),
        bindings=tuple(
            BindingSpec(
                package_format=raw["package_format"],
                task_variables=raw.get("task_variables", {}),
            )
            for raw in _REAL_SPEC["bindings"]
        ),
    )


def test_the_package_against_the_frozen_v2_fixture():
    """The exact partition, measured once and pinned: what PR G's artifact actually says
    about the real draft the corpus holds. `cr-prerequisites-declared` never reaches its
    executor — LearnpackV2 declares no `prerequisites` capability, and unmet demand
    derives `not_applicable` before execution (derivation case (b)). Same case for
    `cr-cognitive-demand-rises-across-the-course` is a different case now: pinned to v8, the
    instrument DOES require the new-shape `lesson_concept_coverage` the fixture carries, so
    the criterion reaches the coverage gate and this artifact abstains from it."""
    outcomes, metrics = derive_and_execute(
        _instrument_spec(), _fixture_profile(), PACKAGE.coverage, dict(PACKAGE.executors)
    )

    assert len(outcomes) == 29
    by_outcome: dict[str, set[str]] = {}
    for outcome in outcomes:
        by_outcome.setdefault(outcome.outcome, set()).add(outcome.criterion_id)

    assert by_outcome["not_applicable"] == {"cr-prerequisites-declared"}
    assert by_outcome["pass"] == {
        "cr-audience-declared",
        "cr-course-has-development",
        "cr-course-opens-with-general-intro",
        "cr-module-structure-well-formed",
        "cr-no-lesson-spikes-in-lexical-load",
        "cr-objectives-min-count",
    }
    # Since this test moved from v7 to v8, `cr-cognitive-demand-rises-across-the-course` does
    # reach the coverage gate and lands in `not_assessed` with the rest of the abstentions.
    # The abstains restricted to what THIS version declares: the artifact also decides
    # ids v9 introduced and one v9 retired, and an outcome exists only for a criterion
    # the pinned version carries.
    declared_here = {outcome.criterion_id for outcome in outcomes}
    assert by_outcome["not_assessed"] == set(PACKAGE.coverage.abstains) & declared_here
    assert "fail" not in by_outcome and "no_evidence" not in by_outcome

    executed = {o.criterion_id: o for o in outcomes if o.outcome == "pass"}
    assert all(not o.derived and o.quote for o in executed.values())

    metric_values = {m.metric_id: m.value for m in metrics}
    assert metric_values["declared_objectives_count"] == 3
    assert "declared_objectives" not in metric_values  # the collision PR G resolves
    assert metric_values["module_count"] == 5
    assert metric_values["development_lessons"] == 10


def test_lexical_load_of_the_v2_fixture_is_pinned():
    """The calibration pin for the copied measure's now-independent identity: what the
    frozen draft actually measures, so the algorithm cannot drift in silence. The closing
    lesson (04.1) is below MIN_WORDS_FOR_A_STABLE_MEAN and is rightly excluded."""
    loads = measures.lexical_load_by_lesson(list(extract_fixture()["lesson_bodies"].value))

    assert len(loads) == 10  # 11 lessons, one too short to carry a stable mean
    median = statistics.median(loads.values())
    worst_slug, worst = max(loads.items(), key=lambda pair: pair[1])
    assert round(median, 3) == 1.460
    assert worst_slug == "04.0-building-a-complete-html-page"
    assert round(worst - median, 3) == 0.108  # under the 0.20 threshold: no spike


# --- the ratification act: what this artifact exists to make possible -----------------


@pytest.fixture
def admin(register_assessor, unique):
    email = f"admin-{unique}@example.com"
    assessor_id = register_assessor(f"user_admin_{unique}", email, "Admin")
    return assessor_id, email


@pytest.fixture
def patched_drafts_package(unique, monkeypatch):
    """The drafts package, cloned onto a throwaway lineage (same coverage)."""
    name = f"drafts-structural-{unique}"
    lineage = f"qa-copy-{unique}"
    package = dataclasses.replace(
        PACKAGE,
        name=name,
        instrument_id=lineage,
        source_config={**PACKAGE.source_config, "name": name, "instrumentId": lineage},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, PACKAGE.version), package)
    return package


def drafts_copy_spec(unique: str, version: str) -> dict:
    file = INSTRUMENTS_DIR / f"course-drafts-qa-{version}.yaml"
    spec = copy.deepcopy(yaml.safe_load(file.read_text(encoding="utf-8")))
    spec["instrument_id"] = f"qa-copy-{unique}"
    return spec


def test_the_real_coverage_ratifies_both_published_versions(
    cleanup, unique, namespace, admin, patched_drafts_package
):
    """PR G's reason to exist, through the real act: a new lineage can ratify nothing until an
    assessor artifact declares itself against it (runbook step 5). One artifact ratifies both
    versions on disk because its coverage is a superset of each."""
    admin_id, email = admin

    v8_id = publish_instrument(cleanup, drafts_copy_spec(unique, "v8"), admin_id)
    assert run_ratify_assessor(patched_drafts_package.name, "1", v8_id, email, []) == 0
    track_automated(cleanup, patched_drafts_package.name)

    with SessionLocal() as session:
        row = SqlAlchemyAssessorRepository(session).get_automated(patched_drafts_package.name, "1")
    assert row is not None
    assert row.source_config == patched_drafts_package.source_config

    v9_id = publish_instrument(cleanup, drafts_copy_spec(unique, "v9"), admin_id)
    assert run_ratify_assessor(patched_drafts_package.name, "1", v9_id, email, []) == 0
