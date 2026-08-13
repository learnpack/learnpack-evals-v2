"""The fitness projection's arithmetic (ADR-0023) — pure, no DB.

The rules under test are the ones that make the number safe to evolve against: which states
enter the denominator, that an empty denominator is undefined rather than zero, that a
criterion is attributed once per quality and fully to each quality, and that a dimension is
the mean of its DEFINED qualities.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.evaluation_studies.application.dtos import (
    BriefInfo,
    ContentInfo,
    CriterionOutcomeInfo,
    GeneratorInfo,
    InstrumentClaim,
    InstrumentCriterion,
    InstrumentInfo,
    JudgmentInfo,
    RatificationInfo,
)
from app.modules.evaluation_studies.application.fitness import (
    FITNESS_FORMULA_VERSION,
    compute_fitness,
    criteria_by_quality,
)
from app.modules.evaluation_studies.domain.model import Study

NOW = datetime(2026, 8, 7, tzinfo=UTC)


def instrument(claims, criteria, quality_dimensions=None) -> InstrumentInfo:
    return InstrumentInfo(
        instrument_version_id="qa-v1",
        status="published",
        claims=tuple(claims),
        criteria=tuple(criteria),
        quality_dimensions=quality_dimensions or {},
    )


def claim(claim_id: str, *quality_ids: str) -> InstrumentClaim:
    return InstrumentClaim(claim_id=claim_id, statement=claim_id, quality_ids=quality_ids)


def criterion(criterion_id: str, *claim_ids: str) -> InstrumentCriterion:
    return InstrumentCriterion(
        criterion_id=criterion_id,
        claim_ids=claim_ids,
        required_data=("datum",),
        on_missing_evidence="no_evidence",
    )


def project(
    inst: InstrumentInfo,
    outcomes_per_content: dict[UUID, dict[str, str]],
    generators_of: dict[UUID, UUID | None] | None = None,
    generators: dict[UUID, GeneratorInfo] | None = None,
    ratifications: list[RatificationInfo] | None = None,
    briefs_of: dict[UUID, UUID | None] | None = None,
    briefs: dict[UUID, BriefInfo] | None = None,
    recipe: list[UUID] | None = None,
) -> dict:
    """Run the projection over hand-written outcomes, one judgment per content."""
    generators_of = generators_of or {}
    briefs_of = briefs_of or {}
    contents, judgments, outcomes = [], [], []
    for content_id, states in outcomes_per_content.items():
        judgment_id = uuid4()
        contents.append(
            ContentInfo(
                content_id=content_id,
                external_id=f"course-{content_id}",
                package_format="LearnpackV1",
                brief_id=briefs_of.get(content_id),
                generator_version_id=generators_of.get(content_id),
            )
        )
        judgments.append(
            JudgmentInfo(
                judgment_id=judgment_id, content_id=content_id, derived_at=NOW, coverage={}
            )
        )
        outcomes.extend(
            CriterionOutcomeInfo(
                judgment_id=judgment_id,
                content_id=content_id,
                criterion_id=criterion_id,
                outcome=outcome,
                derived=False,
            )
            for criterion_id, outcome in states.items()
        )
    study = Study(
        id=uuid4(),
        purpose="fitness",
        status="published",
        instrument_version_id=inst.instrument_version_id,
        brief_ids=tuple(dict.fromkeys(recipe or [b for b in briefs_of.values() if b is not None])),
        content_ids=tuple(outcomes_per_content),
    )
    return compute_fitness(
        study=study,
        instrument=inst,
        contents=contents,
        briefs=briefs or {},
        generators=generators or {},
        judgments=judgments,
        outcomes=outcomes,
        ratifications=ratifications or [],
        computed_at=NOW,
    )


# ------------------------------------------------------------------ attribution


def test_a_criterion_evidencing_two_claims_of_one_quality_counts_once():
    """Deduplication is structural (a set), not a special case: otherwise a criterion would
    weigh twice for the same quality just because two claims cite it."""
    inst = instrument(
        claims=[claim("cl-a", "q1"), claim("cl-b", "q1")],
        criteria=[criterion("cr-shared", "cl-a", "cl-b"), criterion("cr-only-a", "cl-a")],
    )

    assert criteria_by_quality(inst) == {"q1": frozenset({"cr-shared", "cr-only-a"})}

    content = uuid4()
    result = project(inst, {content: {"cr-shared": "fail", "cr-only-a": "pass"}})
    quality = result["contents"][0]["qualities"]["q1"]
    assert quality["coverage"]["criteria"] == 2  # not 3
    assert quality["fitness"] == 0.5


def test_a_claim_about_two_qualities_counts_its_criteria_fully_in_each():
    """Splitting 1/n would make a criterion's weight depend on instrument wording."""
    inst = instrument(
        claims=[claim("cl-arc", "q-start", "q-demand")],
        criteria=[criterion("cr-1", "cl-arc"), criterion("cr-2", "cl-arc")],
    )
    content = uuid4()

    result = project(inst, {content: {"cr-1": "pass", "cr-2": "fail"}})

    qualities = result["contents"][0]["qualities"]
    assert qualities["q-start"]["fitness"] == 0.5
    assert qualities["q-demand"]["fitness"] == 0.5
    assert qualities["q-start"]["coverage"]["criteria"] == 2


# ------------------------------------------------------------------ the denominator


def test_omissions_penalize_and_assessor_limits_do_not():
    """The anti-gaming core: no_evidence is the generator's omission and counts against it;
    not_assessed is our missing executor and execution_error is this run's own failure —
    neither must count, or the fitness would track our tooling instead of the artifact."""
    inst = instrument(
        claims=[claim("cl", "q")],
        criteria=[criterion(f"cr-{i}", "cl") for i in range(1, 6)],
    )
    content = uuid4()

    result = project(
        inst,
        {
            content: {
                "cr-1": "pass",
                "cr-2": "no_evidence",  # in, penalizes
                "cr-3": "not_assessed",  # out
                "cr-4": "not_applicable",  # out
                "cr-5": "execution_error",  # out (ADR-0037 §6)
            }
        },
    )

    quality = result["contents"][0]["qualities"]["q"]
    assert quality["coverage"]["denominator"] == 2
    assert quality["fitness"] == 0.5
    assert quality["coverage"]["notAssessed"] == 1
    assert quality["coverage"]["notApplicable"] == 1
    assert quality["coverage"]["executionError"] == 1


def test_an_unknown_outcome_state_is_loud_never_dropped():
    """The partition must name every state: a silent drop is the NaN failure mode the
    industry already paid for (ADR-0037 §6)."""
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr-1", "cl")])
    content = uuid4()

    with pytest.raises(ValueError, match="unknown outcome state"):
        project(inst, {content: {"cr-1": "half_pass"}})


def test_an_unmeasurable_quality_is_undefined_and_never_zero():
    """Zero would assert that everything measurable failed, when nothing was measurable."""
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr-1", "cl")])
    content = uuid4()

    result = project(inst, {content: {"cr-1": "not_assessed"}})

    quality = result["contents"][0]["qualities"]["q"]
    assert quality["fitness"] is None
    assert quality["coverage"]["denominator"] == 0


# ------------------------------------------------------------------ the roll-up


def test_a_dimension_is_the_mean_of_its_defined_qualities():
    inst = instrument(
        claims=[claim("cl-a", "q1"), claim("cl-b", "q2"), claim("cl-c", "q3")],
        criteria=[criterion("cr-a", "cl-a"), criterion("cr-b", "cl-b"), criterion("cr-c", "cl-c")],
        quality_dimensions={"q1": "d", "q2": "d", "q3": "d"},
    )
    content = uuid4()

    result = project(
        inst,
        {content: {"cr-a": "pass", "cr-b": "fail", "cr-c": "not_applicable"}},
    )

    dimension = result["contents"][0]["dimensions"]["d"]
    # Mean of 1.0 and 0.0 — the undefined q3 is left OUT, not read as a zero (which would
    # have given 0.333 and quietly punished the generator for unmet demand).
    assert dimension["fitness"] == 0.5
    assert dimension["coverage"] == {"qualities": 3, "defined": 2}


def test_a_dimension_with_nothing_measurable_is_undefined():
    inst = instrument(
        claims=[claim("cl", "q")],
        criteria=[criterion("cr", "cl")],
        quality_dimensions={"q": "d"},
    )
    content = uuid4()

    result = project(inst, {content: {"cr": "not_applicable"}})

    assert result["contents"][0]["dimensions"]["d"]["fitness"] is None


def test_a_quality_that_groups_nowhere_scores_but_rolls_up_nowhere():
    inst = instrument(
        claims=[claim("cl-a", "q-grouped"), claim("cl-b", "q-orphan")],
        criteria=[criterion("cr-a", "cl-a"), criterion("cr-b", "cl-b")],
        quality_dimensions={"q-grouped": "d"},  # q-orphan is absent from the frozen map
    )
    content = uuid4()

    result = project(inst, {content: {"cr-a": "pass", "cr-b": "fail"}})

    level = result["contents"][0]
    assert level["qualities"]["q-orphan"]["fitness"] == 0.0
    assert level["qualities"]["q-orphan"]["dimensionId"] is None
    assert level["dimensions"]["d"]["coverage"] == {"qualities": 1, "defined": 1}


# ------------------------------------------------------------------ grains


def test_a_generator_pools_its_contents_instead_of_averaging_them():
    """Contents are samples of one population, so the counts pool. A mean of means would let
    a content with a single defined criterion weigh as much as one with ten."""
    inst = instrument(
        claims=[claim("cl", "q")],
        criteria=[criterion("cr-1", "cl"), criterion("cr-2", "cl")],
    )
    generator_id, thin, thick = uuid4(), uuid4(), uuid4()

    result = project(
        inst,
        {
            thin: {"cr-1": "pass", "cr-2": "not_assessed"},  # 1 defined, passed
            thick: {"cr-1": "fail", "cr-2": "fail"},  # 2 defined, both failed
        },
        generators_of={thin: generator_id, thick: generator_id},
        generators={
            generator_id: GeneratorInfo(
                generator_version_id=generator_id, name="learnpack-generator", version="1.0.0"
            )
        },
    )

    generator = result["generators"][0]
    assert generator["contents"] == 2
    # Pooled: 1 pass over 3 defined criteria. A mean of the two contents would say 0.5.
    assert generator["qualities"]["q"]["fitness"] == round(1 / 3, 6)
    assert generator["name"] == "learnpack-generator"


def test_an_unknown_generator_is_excluded_from_accumulation_and_named():
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr", "cl")])
    known_generator, attributed, unknown = uuid4(), uuid4(), uuid4()

    result = project(
        inst,
        {attributed: {"cr": "pass"}, unknown: {"cr": "fail"}},
        generators_of={attributed: known_generator, unknown: None},
    )

    assert [g["generatorVersionId"] for g in result["generators"]] == [str(known_generator)]
    assert result["generators"][0]["qualities"]["q"]["fitness"] == 1.0
    assert result["unknownExclusions"] == [str(unknown)]
    # The study level keeps it: only generator-level accumulation excludes it (ADR-0024).
    assert result["study"]["qualities"]["q"]["fitness"] == 0.5


# ------------------------------------------------------------------ the brief axis


def brief(brief_id: UUID, text: str, brief_hash: str | None = "sha256:derived") -> BriefInfo:
    return BriefInfo(brief_id=brief_id, brief=text, fields={}, brief_hash=brief_hash)


def test_repeats_of_one_commission_group_without_being_pooled():
    """ADR-0039: the brief labels the content grain and aggregates nothing. Two courses from
    one commission keep their own values — pooling them would erase exactly the dispersion
    the repeats were generated to measure, and nothing recovers it afterwards."""
    inst = instrument(
        claims=[claim("cl", "q")],
        criteria=[criterion("cr-1", "cl"), criterion("cr-2", "cl")],
    )
    commission, other = uuid4(), uuid4()
    first, second, elsewhere = uuid4(), uuid4(), uuid4()

    result = project(
        inst,
        {
            first: {"cr-1": "pass", "cr-2": "pass"},  # same commission, different course
            second: {"cr-1": "pass", "cr-2": "fail"},
            elsewhere: {"cr-1": "fail", "cr-2": "fail"},
        },
        briefs_of={first: commission, second: commission, elsewhere: other},
        briefs={commission: brief(commission, "Teach CSS"), other: brief(other, "Teach Git")},
    )

    by_content = {c["contentId"]: c for c in result["contents"]}
    assert by_content[str(first)]["briefId"] == str(commission)
    assert by_content[str(second)]["briefId"] == str(commission)
    assert by_content[str(elsewhere)]["briefId"] == str(other)
    # The two repeats disagree, and the projection says so instead of averaging them away.
    assert by_content[str(first)]["qualities"]["q"]["fitness"] == 1.0
    assert by_content[str(second)]["qualities"]["q"]["fitness"] == 0.5
    # No fourth grain: the only levels are content, generator version and study.
    assert "briefLevels" not in result
    assert all("qualities" not in entry for entry in result["briefs"])


def test_the_header_names_every_commission_including_one_that_produced_nothing():
    """The table covers the recipe as well as what the contents reference: a generation that
    produced no course is a reading about that commission, not its disappearance."""
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr", "cl")])
    delivered, barren = uuid4(), uuid4()
    content = uuid4()

    result = project(
        inst,
        {content: {"cr": "pass"}},
        briefs_of={content: delivered},
        briefs={
            delivered: brief(delivered, "Teach CSS", "sha256:css"),
            barren: brief(barren, "Teach Rust", "sha256:rust"),
        },
        recipe=[delivered, barren],
    )

    assert result["briefs"] == sorted(
        [
            {"briefId": str(delivered), "briefHash": "sha256:css", "brief": "Teach CSS"},
            {"briefId": str(barren), "briefHash": "sha256:rust", "brief": "Teach Rust"},
        ],
        key=lambda entry: entry["briefId"],
    )
    assert [c["briefId"] for c in result["contents"]] == [str(delivered)]


def test_a_content_without_a_brief_groups_nowhere_and_says_so():
    """An absent brief is a first-class recorded state (ADR-0022 §4), and a manually
    registered one carries no derived hash. Neither is reported as a group of its own."""
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr", "cl")])
    commission, paired, orphan = uuid4(), uuid4(), uuid4()

    result = project(
        inst,
        {paired: {"cr": "pass"}, orphan: {"cr": "fail"}},
        briefs_of={paired: commission, orphan: None},
        briefs={commission: brief(commission, "Registered by hand", brief_hash=None)},
    )

    by_content = {c["contentId"]: c for c in result["contents"]}
    assert by_content[str(orphan)]["briefId"] is None
    assert result["briefs"] == [
        {"briefId": str(commission), "briefHash": None, "brief": "Registered by hand"}
    ]
    # The orphan still counts everywhere else: it is unpaired, not excluded.
    assert result["study"]["qualities"]["q"]["fitness"] == 0.5


def test_a_brief_the_caller_could_not_read_is_still_named():
    """Dropping the row would take the group with it, and identifying the group is what the
    table is for."""
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr", "cl")])
    commission, content = uuid4(), uuid4()

    result = project(inst, {content: {"cr": "pass"}}, briefs_of={content: commission}, briefs={})

    assert result["briefs"] == [{"briefId": str(commission), "briefHash": None, "brief": None}]
    assert result["contents"][0]["briefId"] == str(commission)


def test_only_the_current_judgment_of_a_content_counts():
    """Judgments are append-only; a superseded one must not feed the number the GA reads."""
    inst = instrument(claims=[claim("cl", "q")], criteria=[criterion("cr", "cl")])
    content = uuid4()
    stale, current = uuid4(), uuid4()
    study = Study(
        id=uuid4(),
        purpose="fitness",
        status="published",
        instrument_version_id="qa-v1",
        content_ids=(content,),
    )

    result = compute_fitness(
        study=study,
        instrument=inst,
        contents=[
            ContentInfo(
                content_id=content,
                external_id="course",
                package_format="LearnpackV1",
                brief_id=None,
                generator_version_id=None,
            )
        ],
        briefs={},
        generators={},
        judgments=[
            JudgmentInfo(judgment_id=stale, content_id=content, derived_at=NOW, coverage={}),
            JudgmentInfo(
                judgment_id=current,
                content_id=content,
                derived_at=datetime(2026, 8, 8, tzinfo=UTC),
                coverage={},
            ),
        ],
        outcomes=[
            CriterionOutcomeInfo(
                judgment_id=stale,
                content_id=content,
                criterion_id="cr",
                outcome="fail",
                derived=False,
            ),
            CriterionOutcomeInfo(
                judgment_id=current,
                content_id=content,
                criterion_id="cr",
                outcome="pass",
                derived=False,
            ),
        ],
        ratifications=[],
        computed_at=NOW,
    )

    assert result["contents"][0]["qualities"]["q"]["fitness"] == 1.0
    assert result["contents"][0]["qualities"]["q"]["coverage"]["criteria"] == 1


# ------------------------------------------------------------------ what travels with it


def test_every_value_travels_with_its_formula_version_and_assessor_coverage():
    """Pinning the formula is not enough: dropping not_assessed means two assessor sets
    compute over different populations — and dropping execution_error means two runs of
    the same content can too (ADR-0037 §6) — so the GA may only compare within equal
    coverage, and both counts travel with every value."""
    inst = instrument(
        claims=[claim("cl", "q")], criteria=[criterion("cr", "cl"), criterion("cr-2", "cl")]
    )
    content, assessor = uuid4(), uuid4()

    result = project(
        inst,
        {content: {"cr": "not_assessed", "cr-2": "execution_error"}},
        ratifications=[RatificationInfo(assessor_id=assessor, instrument_version_id="qa-v1")],
    )

    assert result["formulaVersion"] == FITNESS_FORMULA_VERSION
    # Labelling a value is not changing it: the brief axis moved no number, so values
    # computed before it stay comparable with values computed after (ADR-0039 §6).
    assert result["formulaVersion"] == "1"
    assert result["signal"] == "optimization"  # never a judgment
    assert result["assessorCoverage"]["ratifiedAssessors"] == [str(assessor)]
    assert result["assessorCoverage"]["notAssessed"] == 1
    assert result["assessorCoverage"]["executionErrors"] == 1
    assert result["denominatorRule"]["excluded"] == [
        "not_applicable",
        "not_assessed",
        "execution_error",
    ]


def test_a_study_with_nothing_pinned_answers_with_its_gaps():
    """It informs rather than refusing, the way readiness does."""
    study = Study(id=uuid4(), purpose="empty", status="declared")

    result = compute_fitness(
        study=study,
        instrument=None,
        contents=[],
        briefs={},
        generators={},
        judgments=[],
        outcomes=[],
        ratifications=[],
        computed_at=NOW,
    )

    assert [g["gap"] for g in result["gaps"]] == ["instrument_not_pinned", "dataset_not_composed"]
    assert result["study"] == {}
    assert result["briefs"] == []
