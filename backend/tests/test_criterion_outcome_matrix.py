"""The per-criterion matrix — pure, no DB.

The rules under test are the ones that make it readable rather than merely available: that
a criterion has a denominator whether or not anything produced an outcome for it, that the
evidence of a pass travels (nothing else carries it), that a superseded judgment never
sits beside the current one, and that a frozen report — not recency — decides what a
signed-off study is read through.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.evaluation_studies.application.criterion_outcomes import (
    compute_criterion_outcomes,
)
from app.modules.evaluation_studies.application.dtos import (
    AssessorInfo,
    ContentInfo,
    CriterionOutcomeInfo,
    InstrumentClaim,
    InstrumentCriterion,
    InstrumentInfo,
    JudgmentInfo,
)
from app.modules.evaluation_studies.domain.model import Study

NOW = datetime(2026, 8, 14, tzinfo=UTC)

INSTRUMENT = InstrumentInfo(
    instrument_version_id="qa-v1",
    status="published",
    claims=(
        InstrumentClaim("cl-structure", "The course is well structured"),
        InstrumentClaim("cl-objectives", "Objectives are declared"),
    ),
    criteria=(
        InstrumentCriterion("cr-modules", ("cl-structure",), ("lesson_inventory",), "fail"),
        InstrumentCriterion("cr-objectives", ("cl-objectives",), ("learning_objectives",), "fail"),
    ),
)


def content(content_id: UUID) -> ContentInfo:
    return ContentInfo(
        content_id=content_id,
        external_id=f"course-{str(content_id)[:8]}",
        package_format="LearnpackV1",
        brief_id=None,
        generator_version_id=None,
    )


HYBRID_10 = AssessorInfo(assessor_id=uuid4(), name="drafts-hybrid", version="10")


def judgment(
    content_id: UUID, derived_at: datetime = NOW, assessor: AssessorInfo = HYBRID_10
) -> JudgmentInfo:
    return JudgmentInfo(
        judgment_id=uuid4(),
        content_id=content_id,
        derived_at=derived_at,
        coverage={},
        assessor=assessor,
    )


def outcome(
    j: JudgmentInfo, criterion_id: str, state: str, quote: str | None = None, derived: bool = False
) -> CriterionOutcomeInfo:
    return CriterionOutcomeInfo(
        judgment_id=j.judgment_id,
        content_id=j.content_id,
        criterion_id=criterion_id,
        outcome=state,
        derived=derived,
        quote=quote,
    )


def matrix(
    content_ids: list[UUID],
    judgments: list[JudgmentInfo],
    outcomes: list[CriterionOutcomeInfo],
    frozen_report: dict | None = None,
    instrument: InstrumentInfo | None = INSTRUMENT,
) -> dict:
    study = Study(
        id=uuid4(),
        name="a round",
        status="open",
        instrument_version_id="qa-v1",
        content_ids=tuple(content_ids),
    )
    return compute_criterion_outcomes(
        study=study,
        instrument=instrument,
        contents=[content(cid) for cid in content_ids],
        judgments=judgments,
        outcomes=outcomes,
        frozen_report=frozen_report,
        computed_at=NOW,
    )


def section(result: dict, criterion_id: str) -> dict:
    return next(c for c in result["criteria"] if c["criterionId"] == criterion_id)


def test_a_declared_criterion_has_a_denominator_before_anything_produced_an_outcome():
    """The criteria come from the instrument, never from the rows that happen to exist.

    Counting failures over whatever outcomes turned up would answer "which check fails
    most" with a number nobody can compare — the denominator-less count ADR-0011 forbids.
    """
    a, b = uuid4(), uuid4()
    ja = judgment(a)
    result = matrix([a, b], [ja], [outcome(ja, "cr-modules", "fail")])

    modules = section(result, "cr-modules")
    assert modules["coverage"] == {"observed": 1, "of": 2}
    assert modules["distribution"]["fail"] == 1

    # Nothing judged this one anywhere, and it still has a row and a denominator.
    objectives = section(result, "cr-objectives")
    assert objectives["coverage"] == {"observed": 0, "of": 2}
    assert set(objectives["distribution"].values()) == {0}
    assert objectives["outcomes"] == []
    assert result["contentsWithoutJudgment"] == [str(b)]


def test_the_quote_that_grounds_a_pass_travels_here_and_nowhere_else():
    """A finding exists one per FAILING criterion, so the passage a judge read to decide a
    pass has no other way out of the database. This is the whole reason for the resource."""
    cid = uuid4()
    j = judgment(cid)
    result = matrix(
        [cid],
        [j],
        [
            outcome(j, "cr-modules", "pass", quote="Module 1 — Getting started"),
            outcome(j, "cr-objectives", "fail", quote="no objectives declared"),
        ],
    )
    passed = section(result, "cr-modules")["outcomes"][0]
    assert passed["outcome"] == "pass"
    assert passed["quote"] == "Module 1 — Getting started"
    assert section(result, "cr-objectives")["outcomes"][0]["quote"] == "no objectives declared"


def test_a_superseded_judgment_never_sits_beside_the_current_one():
    """Judgments are append-only. Showing both would put two verdicts of one criterion on
    one course side by side, and the reader would have to work out which one counts."""
    cid = uuid4()
    stale = judgment(cid, derived_at=NOW - timedelta(days=1))
    fresh = judgment(cid)
    result = matrix(
        [cid],
        [stale, fresh],
        [outcome(stale, "cr-modules", "fail"), outcome(fresh, "cr-modules", "pass")],
    )
    modules = section(result, "cr-modules")
    assert modules["coverage"]["observed"] == 1
    assert [row["outcome"] for row in modules["outcomes"]] == ["pass"]
    assert result["judgmentBasis"]["basis"] == "current"


def test_a_frozen_report_decides_which_judgment_the_matrix_reads():
    """A signed-off report named its judgments and cannot change. Re-evaluate the course
    afterwards and a newer judgment exists that the report never saw — reading "the latest"
    would show evidence for a document that does not reflect it."""
    cid = uuid4()
    published = judgment(cid, derived_at=NOW - timedelta(days=1))
    later = judgment(cid)
    result = matrix(
        [cid],
        [published, later],
        [outcome(published, "cr-modules", "fail"), outcome(later, "cr-modules", "pass")],
        frozen_report={"judgmentIdsUsed": {str(cid): str(published.judgment_id)}},
    )
    assert result["judgmentBasis"]["basis"] == "signedOffReport"
    assert [row["outcome"] for row in section(result, "cr-modules")["outcomes"]] == ["fail"]
    assert result["contents"][0]["judgmentId"] == str(published.judgment_id)


def test_a_report_that_froze_no_judgment_is_honoured_rather_than_fallen_back_from():
    """Publishing a study nobody evaluated is legitimate, and that report reflects no
    judgment at all. Quietly showing judgments derived afterwards would make the matrix
    disagree with the document it explains."""
    cid = uuid4()
    later = judgment(cid)
    result = matrix(
        [cid],
        [later],
        [outcome(later, "cr-modules", "pass")],
        frozen_report={"judgmentIdsUsed": {}},
    )
    assert result["judgmentBasis"]["basis"] == "signedOffReport"
    assert section(result, "cr-modules")["coverage"] == {"observed": 0, "of": 1}
    assert result["contentsWithoutJudgment"] == [str(cid)]


def test_nothing_is_ever_summed_across_criteria():
    """A cross-criterion total is the single aggregate score ADR-0011 retired: it would
    average a structural check against a semantic one and call the result quality."""
    a, b = uuid4(), uuid4()
    ja, jb = judgment(a), judgment(b)
    result = matrix(
        [a, b],
        [ja, jb],
        [
            outcome(ja, "cr-modules", "pass", quote="ok"),
            outcome(ja, "cr-objectives", "fail", quote="none"),
            outcome(jb, "cr-modules", "pass", quote="ok"),
            outcome(jb, "cr-objectives", "pass", quote="two objectives"),
        ],
    )
    assert set(result) == {
        "studyId",
        "status",
        "instrumentVersionId",
        "computedAt",
        "signal",
        "judgmentBasis",
        "assessorsUsed",
        "gaps",
        "contents",
        "criteria",
        "contentsWithoutJudgment",
    }
    assert result["signal"] == "evidence"
    for criterion in result["criteria"]:
        assert set(criterion["coverage"]) == {"observed", "of"}


def test_the_matrix_names_whose_evidence_it_is_showing():
    """A cell's quote is what SOME judge read, and which judge decides whether two cells of
    one criterion are even the same measurement — so the header names them beside
    `judgmentBasis`, which answers the neighbouring half of the same question."""
    a, b = uuid4(), uuid4()
    other = AssessorInfo(assessor_id=uuid4(), name="drafts-hybrid", version="11")
    ja, jb = judgment(a), judgment(b, assessor=other)
    result = matrix(
        [a, b],
        [ja, jb],
        [outcome(ja, "cr-modules", "pass", quote="ok"), outcome(jb, "cr-modules", "fail", "no")],
    )
    assert [entry["version"] for entry in result["assessorsUsed"]] == ["10", "11"]


def test_a_study_with_nothing_pinned_answers_with_its_gaps():
    """It informs rather than refusing, the way readiness does."""
    study = Study(id=uuid4(), name="a round")
    result = compute_criterion_outcomes(
        study=study,
        instrument=None,
        contents=[],
        judgments=[],
        outcomes=[],
        frozen_report=None,
        computed_at=NOW,
    )
    assert [g["gap"] for g in result["gaps"]] == [
        "instrument_not_pinned",
        "assessor_not_pinned",
        "dataset_not_composed",
    ]
    assert result["criteria"] == [] and result["contents"] == []
