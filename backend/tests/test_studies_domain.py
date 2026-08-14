"""Study invariants (13-code §10): pin once · dataset fixed at open · publish immutable.

Pure domain — no DB, no fixtures. The report/matching/readiness composition is specified
here too once it lands (also pure, over local DTOs).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.evaluation_studies.domain.model import (
    DatasetEmpty,
    DatasetLocked,
    InstrumentAlreadyPinned,
    InstrumentNotPinned,
    InvalidStudy,
    Study,
    StudyAlreadyOpen,
    StudyAlreadyPublished,
    StudyNotOpen,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def study(**overrides) -> Study:
    defaults = {"id": uuid4(), "purpose": "First LearnpackV1 QA round"}
    return Study(**{**defaults, **overrides})


def composed_study() -> Study:
    s = study()
    s.pin_instrument("learnpack-course-qa-v1")
    s.compose_dataset((uuid4(),), (uuid4(), uuid4()))
    return s


def open_study() -> Study:
    s = composed_study()
    s.open(NOW)
    return s


# ----------------------------------------------------------------------- declaration


def test_a_study_declares_with_a_purpose():
    s = study()
    assert s.status == "declared"
    assert s.instrument_version_id is None


def test_a_blank_purpose_is_invalid():
    with pytest.raises(InvalidStudy):
        study(purpose="   ")


# ----------------------------------------------------------------------- pin once


def test_the_pin_happens_once():
    s = study()
    s.pin_instrument("learnpack-course-qa-v1")

    with pytest.raises(InstrumentAlreadyPinned):
        s.pin_instrument("learnpack-course-qa-v2")
    assert s.instrument_version_id == "learnpack-course-qa-v1"


def test_the_pin_is_immutable_after_open():
    s = open_study()
    with pytest.raises(InstrumentAlreadyPinned):
        s.pin_instrument("another-version")


# ----------------------------------------------------------------------- prepared is derived


def test_prepared_derives_from_pin_then_compose():
    s = study()
    s.pin_instrument("v1")
    assert s.status == "declared"
    s.compose_dataset((), (uuid4(),))
    assert s.status == "prepared"


def test_prepared_derives_from_compose_then_pin():
    s = study()
    s.compose_dataset((uuid4(),), (uuid4(),))
    assert s.status == "declared"
    s.pin_instrument("v1")
    assert s.status == "prepared"


def test_the_recipe_evolves_freely_before_open():
    s = composed_study()
    replacement = (uuid4(),)
    s.compose_dataset((), replacement)
    assert s.content_ids == replacement
    assert s.brief_ids == ()


# ----------------------------------------------------------------------- dataset fixed at open


def test_open_fixes_the_dataset():
    s = open_study()
    with pytest.raises(DatasetLocked):
        s.compose_dataset((), (uuid4(),))


def test_open_requires_the_pin():
    s = study()
    s.compose_dataset((), (uuid4(),))
    with pytest.raises(InstrumentNotPinned):
        s.open(NOW)


def test_open_requires_a_dataset():
    s = study()
    s.pin_instrument("v1")
    with pytest.raises(DatasetEmpty):
        s.open(NOW)


def test_open_happens_once():
    s = open_study()
    with pytest.raises(StudyAlreadyOpen):
        s.open(NOW)


def test_open_records_when():
    s = composed_study()
    s.open(NOW)
    assert s.status == "open"
    assert s.opened_at == NOW


# ----------------------------------------------------------------------- publish immutable


def test_publish_requires_an_open_round():
    s = composed_study()
    with pytest.raises(StudyNotOpen):
        s.publish(uuid4(), NOW)


def test_publish_records_the_human_act():
    s = open_study()
    who = uuid4()
    s.publish(who, NOW)
    assert s.status == "published"
    assert s.published_by == who
    assert s.published_at == NOW


def test_published_is_immutable():
    s = open_study()
    s.publish(uuid4(), NOW)

    with pytest.raises(StudyAlreadyPublished):
        s.publish(uuid4(), NOW)
    with pytest.raises(StudyAlreadyPublished):
        s.open(NOW)
    with pytest.raises(StudyAlreadyPublished):
        s.compose_dataset((), (uuid4(),))
    with pytest.raises(InstrumentAlreadyPinned):
        s.pin_instrument("another")


# ======================================================================= report composition

from datetime import timedelta  # noqa: E402

from app.modules.evaluation_studies.application.dtos import (  # noqa: E402
    AssessorInfo,
    BriefInfo,
    CapabilityInfo,
    ClaimJudgment,
    ContentInfo,
    FindingInfo,
    GeneratorInfo,
    InstrumentClaim,
    InstrumentCriterion,
    InstrumentInfo,
    JudgmentInfo,
    RatificationInfo,
)
from app.modules.evaluation_studies.application.queries import (  # noqa: E402
    compute_matching,
    compute_readiness,
)
from app.modules.evaluation_studies.application.report import (  # noqa: E402
    compose_preview,
    compose_report,
    latest_judgments,
)

INSTRUMENT = InstrumentInfo(
    instrument_version_id="qa-v1",
    status="published",
    claims=(
        InstrumentClaim("cl-structure", "The course is well structured"),
        InstrumentClaim("cl-objectives", "Objectives are declared"),
    ),
    criteria=(
        InstrumentCriterion("cr-modules", ("cl-structure",), ("lesson_inventory",), "fail"),
        InstrumentCriterion("cr-bodies", ("cl-structure",), ("lesson_bodies",), "no_evidence"),
        InstrumentCriterion("cr-objectives", ("cl-objectives",), ("learning_objectives",), "fail"),
    ),
)

CAPABILITY = CapabilityInfo(
    package_format="LearnpackV1",
    adapter_version="2",
    capabilities=("lesson_inventory", "lesson_bodies"),
    accepted=True,
)

BASIS_OK = {"pass": 2, "fail": 0, "noEvidence": 0, "notApplicable": 0, "notAssessed": 0}
BASIS_FAIL = {"pass": 1, "fail": 1, "noEvidence": 0, "notApplicable": 0, "notAssessed": 0}
BASIS_NOT_ASSESSED = {"pass": 1, "fail": 0, "noEvidence": 0, "notApplicable": 0, "notAssessed": 1}
BASIS_NO_EVIDENCE = {"pass": 0, "fail": 0, "noEvidence": 1, "notApplicable": 0, "notAssessed": 0}
BASIS_MIXED = {"pass": 0, "fail": 0, "noEvidence": 1, "notApplicable": 0, "notAssessed": 1}
# Judgments derived since ADR-0037 carry the sixth key; the report reads both shapes.
BASIS_EXECUTION_ERROR = {
    "pass": 1,
    "fail": 0,
    "noEvidence": 0,
    "notApplicable": 0,
    "notAssessed": 0,
    "executionError": 1,
}


HYBRID_10 = AssessorInfo(assessor_id=uuid4(), name="drafts-hybrid", version="10")
HYBRID_11 = AssessorInfo(assessor_id=uuid4(), name="drafts-hybrid", version="11")


def judgment(content_id, *claims, derived_at=NOW, excluded=(), assessor=HYBRID_10):
    return JudgmentInfo(
        judgment_id=uuid4(),
        content_id=content_id,
        derived_at=derived_at,
        coverage={"criteria": {}, "excludedClaims": list(excluded)},
        claims=tuple(claims),
        assessor=assessor,
    )


def published_study(content_ids, brief_ids=()):
    s = study()
    s.pin_instrument("qa-v1")
    s.compose_dataset(tuple(brief_ids), tuple(content_ids))
    s.open(NOW)
    s.publish(uuid4(), NOW)
    return s


def content(content_id, brief_id=None, generator_version_id=None):
    return ContentInfo(
        content_id=content_id,
        external_id=f"course-{str(content_id)[:8]}",
        package_format="LearnpackV1",
        brief_id=brief_id,
        generator_version_id=generator_version_id,
    )


def test_the_report_uses_the_latest_judgment_per_content():
    cid = uuid4()
    older = judgment(
        cid,
        ClaimJudgment("cl-structure", "refuted", BASIS_FAIL),
        derived_at=NOW - timedelta(days=1),
    )
    newer = judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK))

    current = latest_judgments([older, newer])
    assert current[cid].judgment_id == newer.judgment_id

    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[older, newer],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    assert report["judgmentIdsUsed"] == {str(cid): str(newer.judgment_id)}
    assert report["contents"][0]["claims"][0]["status"] == "supported"


def test_the_report_names_the_assessor_behind_every_judgment():
    """`judgmentIdsUsed` pins WHICH judgments; without this it never pinned WHOSE — and a
    uuid minted in one store means nothing in another, which is why the artifact's
    `name:version` travels beside it (ADR-0042 §1)."""
    cid, other = uuid4(), uuid4()
    report = compose_report(
        study=published_study([cid, other]),
        contents=[content(cid), content(other)],
        briefs={},
        generators={},
        judgments=[judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK))],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    judged, unjudged = sorted(report["contents"], key=lambda c: c["judgmentId"] is None)
    assert judged["assessor"] == {
        "assessorId": str(HYBRID_10.assessor_id),
        "name": "drafts-hybrid",
        "version": "10",
    }
    # Present and null, never absent: a consumer reads one shape whether or not a course
    # was judged, and "nobody judged this" is a fact rather than a missing key.
    assert unjudged["assessor"] is None
    assert report["assessorsUsed"] == [judged["assessor"]]
    assert report["schemaVersion"] == 2


def test_two_assessors_over_one_dataset_is_a_caveat_and_not_a_silence():
    """The state this exists to make visible: half a study judged by `:10`, three courses
    repaired with `:11`, published. Every distribution in that document pools two
    populations, and nothing else in it can say so."""
    a, b = uuid4(), uuid4()
    report = compose_report(
        study=published_study([a, b]),
        contents=[content(a), content(b)],
        briefs={},
        generators={},
        judgments=[
            judgment(a, ClaimJudgment("cl-structure", "supported", BASIS_OK)),
            judgment(b, ClaimJudgment("cl-structure", "refuted", BASIS_FAIL), assessor=HYBRID_11),
        ],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    assert [a["version"] for a in report["assessorsUsed"]] == ["10", "11"]
    assert [a["version"] for a in report["caveats"]["mixedAssessors"]["assessors"]] == ["10", "11"]
    assert report["caveats"]["mixedAssessors"]["note"]


def test_repeats_by_one_assessor_are_one_author_not_two():
    """Two versions of one artifact are two assessors; two runs of one artifact are one.
    The distinction is the assessor's ID, never the count of judgments — which is what
    keeps re-evaluating a course off the caveat it has nothing to do with."""
    cid = uuid4()
    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[
            judgment(
                cid,
                ClaimJudgment("cl-structure", "refuted", BASIS_FAIL),
                derived_at=NOW - timedelta(days=1),
            ),
            judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK)),
        ],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    assert len(report["assessorsUsed"]) == 1
    assert report["caveats"]["mixedAssessors"]["assessors"] == []


def test_a_superseded_judgment_takes_its_author_out_of_the_report_with_it():
    """`assessorsUsed` is computed over the CURRENT judgments, so an assessor whose every
    judgment was replaced is not named — the report says who it reflects, not who ever
    touched the dataset."""
    cid = uuid4()
    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[
            judgment(
                cid,
                ClaimJudgment("cl-structure", "refuted", BASIS_FAIL),
                derived_at=NOW - timedelta(days=1),
                assessor=HYBRID_11,
            ),
            judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK)),
        ],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    assert [a["version"] for a in report["assessorsUsed"]] == ["10"]
    assert report["caveats"]["mixedAssessors"]["assessors"] == []


def test_insufficiency_is_qualified_by_cause():
    cid = uuid4()
    j = judgment(
        cid,
        ClaimJudgment("cl-structure", "insufficient", BASIS_NOT_ASSESSED),
        ClaimJudgment("cl-objectives", "insufficient", BASIS_NO_EVIDENCE),
    )
    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[j],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    causes = {c["claimId"]: c["insufficiencyCause"] for c in report["contents"][0]["claims"]}
    assert causes == {"cl-structure": "not_assessed", "cl-objectives": "no_evidence"}
    caveat_causes = {(c["claimId"], c["cause"]) for c in report["caveats"]["insufficientEvidence"]}
    assert caveat_causes == {
        ("cl-structure", "not_assessed"),
        ("cl-objectives", "no_evidence"),
    }


def test_execution_error_is_a_named_insufficiency_cause_and_a_caveat():
    cid = uuid4()
    j = JudgmentInfo(
        judgment_id=uuid4(),
        content_id=cid,
        derived_at=NOW,
        coverage={"criteria": {"executionError": 2}, "excludedClaims": []},
        claims=(
            ClaimJudgment("cl-structure", "insufficient", BASIS_EXECUTION_ERROR),
            ClaimJudgment(
                "cl-objectives",
                "insufficient",
                BASIS_EXECUTION_ERROR | {"noEvidence": 1},
            ),
        ),
    )
    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[j],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    causes = {c["claimId"]: c["insufficiencyCause"] for c in report["contents"][0]["claims"]}
    # Never "unknown": the run's failure is a named cause; two causes at once read mixed.
    assert causes == {"cl-structure": "execution_error", "cl-objectives": "mixed"}
    assert report["caveats"]["executionErrors"]["perContent"] == [
        {"contentId": str(cid), "count": 2}
    ]


def test_a_quoteless_finding_shows_its_cause():
    cid = uuid4()
    j = judgment(cid, ClaimJudgment("cl-objectives", "refuted", BASIS_FAIL))
    derived_fail = FindingInfo(
        finding_id=uuid4(),
        judgment_id=j.judgment_id,
        content_id=cid,
        claim_id="cl-objectives",
        criterion_id="cr-objectives",
        failure_mode="required data absent: learning_objectives",
        quote=None,
        locator=None,
    )
    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[j],
        findings=[derived_fail],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    finding = report["contents"][0]["findings"][0]
    assert finding["quote"] is None
    assert finding["quoteAbsentCause"] == "required data absent"


def test_unknown_generators_stay_out_of_generator_level():
    known_gen = uuid4()
    linked, orphan = uuid4(), uuid4()
    judgments = [
        judgment(linked, ClaimJudgment("cl-structure", "supported", BASIS_OK)),
        judgment(orphan, ClaimJudgment("cl-structure", "supported", BASIS_OK)),
    ]
    report = compose_report(
        study=published_study([linked, orphan]),
        contents=[content(linked, generator_version_id=known_gen), content(orphan)],
        briefs={},
        generators={known_gen: GeneratorInfo(known_gen, "learnpack-generator", "1.0.0")},
        judgments=judgments,
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    assert len(report["generatorLevel"]) == 1
    section = report["generatorLevel"][0]
    assert section["generatorVersionId"] == str(known_gen)
    assert section["contentsCounted"] == 1
    assert report["caveats"]["unknownExclusions"]["contentIds"] == [str(orphan)]


def test_generator_level_distributes_per_claim_with_coverage():
    gen = uuid4()
    a, b, c = uuid4(), uuid4(), uuid4()
    judgments = [
        judgment(a, ClaimJudgment("cl-structure", "supported", BASIS_OK)),
        judgment(
            b,
            ClaimJudgment("cl-structure", "refuted", BASIS_FAIL),
            excluded=["cl-objectives"],
        ),
        # c never evaluated
    ]
    report = compose_report(
        study=published_study([a, b, c]),
        contents=[
            content(a, generator_version_id=gen),
            content(b, generator_version_id=gen),
            content(c, generator_version_id=gen),
        ],
        briefs={},
        generators={gen: GeneratorInfo(gen, "learnpack-generator", "1.0.0")},
        judgments=judgments,
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    per_claim = {p["claimId"]: p for p in report["generatorLevel"][0]["perClaim"]}

    structure = per_claim["cl-structure"]
    assert structure["distribution"] == {"supported": 1, "refuted": 1, "insufficient": 0}
    assert structure["coverage"] == {"evaluated": 2, "of": 3}
    assert structure["notEvaluated"] == 1

    objectives = per_claim["cl-objectives"]
    assert objectives["excludedNotApplicable"] == 1  # out of the denominator (ADR-0011)
    assert objectives["coverage"]["of"] == 3
    # Never a cross-claim aggregate: nothing sums across claims.
    assert "score" not in report["generatorLevel"][0]
    assert "score" not in structure


def test_a_preview_is_the_report_it_would_write_minus_the_act_that_did_not_happen():
    """The guarantee that makes a preview worth reading: the same composition, so what the
    console shows is what publishing writes.

    Structural on purpose. The day somebody adds a key to `compose_report`, this fails
    unless the preview learned it too — which is the only way a preview stays a preview
    rather than drifting into a second, similar-looking document.
    """
    cid = uuid4()
    inputs = {
        "study": published_study([cid]),
        "contents": [content(cid, generator_version_id=uuid4())],
        "briefs": {},
        "generators": {},
        "judgments": [judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK))],
        "findings": [],
        "capabilities": {"LearnpackV1": CAPABILITY},
        "instrument": INSTRUMENT,
    }
    published = compose_report(**inputs, published_at=NOW)
    preview = compose_preview(**inputs, composed_at=NOW)

    markers = {"documentKind", "composedAt", "frozenRecord", "gaps"}
    assert set(preview) - markers == set(published) - {"publishedAt"}
    for key in set(published) - {"publishedAt"}:
        assert preview[key] == published[key], key
    assert preview["documentKind"] == "preview"
    assert preview["gaps"] == []


def test_a_preview_never_says_it_was_published_even_when_the_study_was():
    """`compose_report` emits `publishedAt` unconditionally and the console renders it
    unguarded, so a preview carrying the composition's clock would read "Published <now>"
    about a study nobody published — and a preview of an ALREADY published study would
    claim the recomposition's clock as the act's.

    The key is absent rather than null: a null renders as the epoch.
    """
    cid = uuid4()
    preview = compose_preview(
        study=published_study([cid]),
        contents=[content(cid)],
        briefs={},
        generators={},
        judgments=[judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK))],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        composed_at=NOW,
    )
    assert "publishedAt" not in preview
    assert preview["composedAt"] == NOW.isoformat()
    # The frozen record exists — and the preview says so instead of impersonating it.
    assert preview["frozenRecord"]["exists"] is True
    assert preview["frozenRecord"]["note"]


def test_a_study_with_nothing_pinned_previews_with_its_gaps_and_every_caveat_kind():
    """It informs rather than refusing, the way readiness does. And the caveat kinds are
    all present at every status: a consumer that walks them must not have to work out
    which of two shapes it is holding."""
    preview = compose_preview(
        study=study(),
        contents=[],
        briefs={},
        generators={},
        judgments=[],
        findings=[],
        capabilities={},
        instrument=None,
        composed_at=NOW,
    )
    assert [g["gap"] for g in preview["gaps"]] == [
        "instrument_not_pinned",
        "dataset_not_composed",
    ]
    assert preview["contents"] == [] and preview["generatorLevel"] == []
    assert preview["judgmentIdsUsed"] == {}
    assert "publishedAt" not in preview
    assert preview["frozenRecord"]["exists"] is False
    assert set(preview["caveats"]) == {
        "insufficientEvidence",
        "unresolvedDisagreements",
        "unknownExclusions",
        "unacceptedAdapters",
        "briefCompleteness",
        "contentsWithoutJudgment",
        "taskVariablePatterns",
        "executionErrors",
        "mixedAssessors",
    }


def test_the_unpinned_preview_has_the_same_keys_as_the_pinned_one():
    """The no-instrument branch is a hand-written literal, not a call to `compose_report`,
    and that is the whole hazard: a key added to the document reaches it only if somebody
    remembers. A consumer that walks the document must read ONE shape at every status, or
    it learns to guess — so the two previews are compared key for key here, which is the
    check the published-vs-preview test performs only for a study that pins something."""
    cid = uuid4()
    common = {
        "contents": [content(cid)],
        "briefs": {},
        "generators": {},
        "judgments": [judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK))],
        "findings": [],
        "capabilities": {"LearnpackV1": CAPABILITY},
        "composed_at": NOW,
    }
    pinned = compose_preview(study=published_study([cid]), instrument=INSTRUMENT, **common)
    unpinned = compose_preview(study=study(), instrument=None, **common)

    assert set(unpinned) == set(pinned)
    assert set(unpinned["caveats"]) == set(pinned["caveats"])


def test_a_pinned_version_that_cannot_be_read_is_its_own_gap():
    """Distinct from "not pinned": one is a study nobody finished setting up, the other is
    a fault — the version it names is gone."""
    s = study()
    s.pin_instrument("qa-v1")
    s.compose_dataset((), (uuid4(),))
    preview = compose_preview(
        study=s,
        contents=[],
        briefs={},
        generators={},
        judgments=[],
        findings=[],
        capabilities={},
        instrument=None,
        composed_at=NOW,
    )
    assert [g["gap"] for g in preview["gaps"]] == ["instrument_not_found"]


def test_every_caveat_kind_is_always_present():
    cid = uuid4()
    report = compose_report(
        study=published_study([cid]),
        contents=[content(cid, generator_version_id=uuid4())],
        briefs={},
        generators={},
        judgments=[judgment(cid, ClaimJudgment("cl-structure", "supported", BASIS_OK))],
        findings=[],
        capabilities={"LearnpackV1": CAPABILITY},
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    caveats = report["caveats"]
    assert set(caveats) == {
        "insufficientEvidence",
        "unresolvedDisagreements",
        "unknownExclusions",
        "unacceptedAdapters",
        "briefCompleteness",
        "contentsWithoutJudgment",
        "taskVariablePatterns",
        "executionErrors",
        "mixedAssessors",
    }
    assert caveats["unresolvedDisagreements"] == []  # inert, present on purpose
    assert caveats["taskVariablePatterns"]["status"] == "deferred"  # non-silent deferral
    assert caveats["executionErrors"]["perContent"] == []  # present even when empty
    assert caveats["mixedAssessors"]["assessors"] == []  # one author is not a caveat


def test_caveats_carry_brief_completeness_and_adapter_acceptance():
    cid = uuid4()
    brief_id = uuid4()
    report = compose_report(
        study=published_study([cid], brief_ids=[brief_id]),
        contents=[content(cid, brief_id=brief_id)],
        briefs={
            brief_id: BriefInfo(
                brief_id=brief_id,
                brief="Create a course.",
                fields={"origin": "ai_derived_syllabus", "promptRecorded": False},
            )
        },
        generators={},
        judgments=[],
        findings=[],
        capabilities={
            "LearnpackV1": CapabilityInfo("LearnpackV1", "2", ("lesson_inventory",), False)
        },
        instrument=INSTRUMENT,
        published_at=NOW,
    )
    caveats = report["caveats"]
    assert caveats["briefCompleteness"] == [
        {"briefId": str(brief_id), "promptRecorded": False, "origin": "ai_derived_syllabus"}
    ]
    assert caveats["unacceptedAdapters"] == [
        {"packageFormat": "LearnpackV1", "adapterVersion": "2"}
    ]
    assert caveats["contentsWithoutJudgment"] == [str(cid)]


# ======================================================================= matching (§6)


def test_matching_reports_the_unmet_demand():
    result = compute_matching(INSTRUMENT, CAPABILITY, "LearnpackV1")

    assert result["extractionAccepted"] is True
    by_criterion = {c["criterionId"]: c for c in result["criteria"]}
    assert by_criterion["cr-modules"]["covered"] is True
    assert by_criterion["cr-objectives"]["covered"] is False
    assert by_criterion["cr-objectives"]["missingData"] == ["learning_objectives"]
    # ADR-0017: the systemic gap is stated once, at the matching level.
    assert result["unmetDemand"] == [
        {"dataRequirementId": "learning_objectives", "criterionIds": ["cr-objectives"]}
    ]
    by_claim = {c["claimId"]: c for c in result["claims"]}
    assert by_claim["cl-structure"] == {
        "claimId": "cl-structure",
        "criteria": 2,
        "coveredCriteria": 2,
    }
    assert by_claim["cl-objectives"] == {
        "claimId": "cl-objectives",
        "criteria": 1,
        "coveredCriteria": 0,
    }


def test_matching_without_an_adapter_leaves_everything_unmet():
    result = compute_matching(INSTRUMENT, None, "UnknownFormatV9")

    assert result["adapterVersion"] is None
    assert result["extractionAccepted"] is None
    assert all(not c["covered"] for c in result["criteria"])


# ======================================================================= readiness (§6)


def test_readiness_names_the_study_gaps():
    s = study()
    result = compute_readiness(s, None, {}, [], [])

    gaps = {g["gap"] for g in result["studyGaps"]}
    assert gaps == {"instrument_not_pinned", "dataset_not_composed"}
    assert result["informative"] is True


def test_readiness_flags_the_missing_ratification():
    s = composed_study()  # pins qa-v1 (see helper)
    s2 = composed_study()

    unratified = compute_readiness(s, INSTRUMENT, {"LearnpackV1": CAPABILITY}, [], ["LearnpackV1"])
    assert {"gap": "no_ratified_assessor", "instrumentVersionId": "learnpack-course-qa-v1"} in (
        unratified["studyGaps"]
    )

    ratified = compute_readiness(
        s2,
        INSTRUMENT,
        {"LearnpackV1": CAPABILITY},
        [RatificationInfo(uuid4(), "learnpack-course-qa-v1")],
        ["LearnpackV1"],
    )
    assert all(g["gap"] != "no_ratified_assessor" for g in ratified["studyGaps"])


def test_readiness_reports_gaps_per_claim():
    s = composed_study()
    lonely_claim = InstrumentInfo(
        instrument_version_id="qa-v1",
        status="published",
        claims=INSTRUMENT.claims + (InstrumentClaim("cl-orphan", "No criteria evidence me"),),
        criteria=INSTRUMENT.criteria,
    )
    result = compute_readiness(
        s,
        lonely_claim,
        {"LearnpackV1": CapabilityInfo("LearnpackV1", "2", ("lesson_inventory",), False)},
        [RatificationInfo(uuid4(), "learnpack-course-qa-v1")],
        ["LearnpackV1"],
    )

    by_claim = {c["claimId"]: c["gaps"] for c in result["claims"]}
    assert {"gap": "claim_without_criteria"} in by_claim["cl-orphan"]
    structure_gaps = by_claim["cl-structure"]
    assert any(
        g["gap"] == "criterion_without_datum_in_format" and g["criterionId"] == "cr-bodies"
        for g in structure_gaps
    )
    assert any(g["gap"] == "extraction_not_accepted" for g in structure_gaps)
