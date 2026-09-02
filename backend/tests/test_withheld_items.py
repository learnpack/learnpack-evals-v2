"""Which items of the human reference are put to a rater (ADR-0053) — pure, no DB.

The rule is one function on the published snapshot, because the screen and the submit path
both read it and a disagreement between them would break the `Evaluation` aggregate's
exact-coverage invariant at the moment somebody presses submit.
"""

from app.modules.evaluation_design.application.dtos import RubricItemDTO, RubricSnapshot

DECLARED = "declared_structured"
ABSENT = "absent"


def item(quality_id: str, *required: str) -> RubricItemDTO:
    return RubricItemDTO(
        quality_id=quality_id,
        order=1,
        dimension="d",
        prompt="p",
        guidance="g",
        anchor_low="lo",
        anchor_high="hi",
        grounded_in=[],
        eligible_sources=["HumanExpert"],
        required_data=list(required),
    )


def rubric(*items: RubricItemDTO) -> RubricSnapshot:
    return RubricSnapshot(
        rubric_version_id="ref-v2",
        rubric_id="ref",
        version="v2",
        name="Reference",
        status="published",
        scope=None,
        scale_min=1,
        scale_max=5,
        response_format="likert",
        items=list(items),
    )


def test_an_item_naming_no_datum_is_always_asked():
    """Eight of the twelve name nothing: they are about what the course does, not what it
    declares, so no profile can settle them."""
    snapshot = rubric(item("coherence-reinforcement"))

    assert snapshot.withheld({"learning_objectives": ABSENT}) == {}
    assert [c.quality_id for c in snapshot.asked({})] == ["coherence-reinforcement"]


def test_a_datum_no_adapter_declares_withholds_without_a_score():
    """No entry at all: the format has no field for it (ADR-0017), so nobody could have
    declared it. The automated side derives `not_applicable`, out of the denominator — this
    must not look like an omission, so there is no score to record."""
    snapshot = rubric(item("objectives-observable", "learning_objectives"))

    # A LearnpackV1 profile: five entries, none of them this one.
    declared = {"course_descriptor": DECLARED, "lesson_bodies": DECLARED}

    assert snapshot.withheld(declared) == {"objectives-observable": None}
    assert snapshot.asked(declared) == []


def test_a_datum_the_course_could_declare_and_did_not_withholds_at_the_bottom():
    """An explicit `absent`: the adapter looked and the course said nothing. The automated
    side derives a penalising outcome, so the human record says the same."""
    snapshot = rubric(item("objectives-observable", "learning_objectives"))

    assert snapshot.withheld({"learning_objectives": ABSENT}) == {"objectives-observable": 1}


def test_capability_is_read_before_absence():
    """Both cases at once, on one item. Read the other way round, a course whose format
    cannot express objectives is indistinguishable from one that omitted them."""
    snapshot = rubric(item("alignment-assessment", "learning_objectives", "prerequisites"))

    # `learning_objectives` is absent AND `prerequisites` has no entry: no capability wins.
    assert snapshot.withheld({"learning_objectives": ABSENT}) == {"alignment-assessment": None}


def test_a_declared_datum_is_asked():
    snapshot = rubric(item("objectives-observable", "learning_objectives"))
    declared = {"learning_objectives": DECLARED}

    assert snapshot.withheld(declared) == {}
    assert [c.quality_id for c in snapshot.asked(declared)] == ["objectives-observable"]


def test_without_an_ok_profile_every_item_is_asked():
    """An unknown fact is not an absent datum (ADR-0053 §2). A content that was never
    profiled, or whose profiling failed, says nothing about what it declares — and
    withholding on silence is the same lie in the other direction."""
    snapshot = rubric(
        item("objectives-observable", "learning_objectives"),
        item("coherence-reinforcement"),
    )

    assert snapshot.withheld({}) == {}
    assert len(snapshot.asked({})) == 2
