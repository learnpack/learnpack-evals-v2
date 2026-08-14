"""StudyReport composition — pure, over local DTOs (13-code §3.6, ADR-0006 style).

Composed at publish and materialized immutable, recording the judgment ids used. Content:
per content, claims with status; at generator level, the distribution of claim status
across the dataset — **never a cross-claim aggregate** (ADR-0011), and every distribution
travels with its coverage (ADR-0011 clause 3). Caveats are ALWAYS present, every kind,
even when empty: publishing with caveats is legitimate and visible; publishing silently,
impossible (12-define invariant 4).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.evaluation_studies.application.dtos import (
    AssessorInfo,
    BriefInfo,
    CapabilityInfo,
    ContentInfo,
    FindingInfo,
    GeneratorInfo,
    InstrumentInfo,
    JudgmentInfo,
)
from app.modules.evaluation_studies.domain.model import Study

# 2 since the report names the assessor behind every judgment (ADR-0042). Reports frozen at
# 1 carry no `assessor`, no `assessorsUsed` and no `mixedAssessors` caveat, and are read as
# the records they are: the absence is a schema fact, not a study with no author.
SCHEMA_VERSION = 2

# ADR-0021: the fail derived from absence carries no quote; the report must show its cause
# so it is not read as an incomplete finding.
QUOTE_ABSENT_CAUSE = "required data absent"

PREVIEW_NOTE = (
    "a preview is recomposed from today's data; once the study is published the record is "
    "the frozen report, and only that report is the study's result"
)


def latest_judgments(judgments: list[JudgmentInfo]) -> dict[UUID, JudgmentInfo]:
    """Judgments are append-only; the most recent per content is the current one."""
    current: dict[UUID, JudgmentInfo] = {}
    for judgment in sorted(judgments, key=lambda j: (j.derived_at, str(j.judgment_id))):
        current[judgment.content_id] = judgment
    return current


def _assessor_section(assessor: AssessorInfo | None) -> dict[str, Any] | None:
    """Whose judgment this is, in both forms (ADR-0042 §1)."""
    if assessor is None:
        return None
    return {
        "assessorId": str(assessor.assessor_id),
        "name": assessor.name,
        "version": assessor.version,
    }


def assessors_used(current: dict[UUID, JudgmentInfo]) -> list[dict[str, Any]]:
    """The distinct authors of a set of current judgments — public, like `latest_judgments`.

    Public because the fitness projection publishes the same list for the same reason, and
    two implementations of "who judged this study" could disagree about a study while
    sitting on one screen.

    Ordered by the pair that reads, not by the uuid: a person scanning the header is
    looking for `drafts-hybrid:10`, and a report that lists two assessors is a report whose
    numbers pool two populations — which is what the `mixedAssessors` caveat says out loud.
    """
    by_id: dict[UUID, AssessorInfo] = {
        judgment.assessor.assessor_id: judgment.assessor
        for judgment in current.values()
        if judgment.assessor is not None
    }
    ordered = sorted(by_id.values(), key=lambda a: (a.display_name, str(a.assessor_id)))
    return [section for a in ordered if (section := _assessor_section(a)) is not None]


def _insufficiency_cause(evidence_basis: dict[str, int]) -> str:
    """Qualify an `insufficient` by its cause (ADR-0018 + ADR-0037: better generator,
    better assessor, better run). `.get` because judgments derived before ADR-0037 carry
    no `executionError` key — an absent count is a zero, not an unknown."""
    causes = [
        cause
        for key, cause in (
            ("noEvidence", "no_evidence"),
            ("notAssessed", "not_assessed"),
            ("executionError", "execution_error"),
        )
        if evidence_basis.get(key, 0) > 0
    ]
    if len(causes) > 1:
        return "mixed"
    if causes:
        return causes[0]
    return "unknown"


def _claim_section(judgment: JudgmentInfo) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for claim in judgment.claims:
        entry: dict[str, Any] = {
            "claimId": claim.claim_id,
            "status": claim.status,
            "evidenceBasis": claim.evidence_basis,
        }
        if claim.status == "insufficient":
            entry["insufficiencyCause"] = _insufficiency_cause(claim.evidence_basis)
        claims.append(entry)
    return claims


def _finding_section(findings: list[FindingInfo]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for finding in findings:
        entry: dict[str, Any] = {
            "findingId": str(finding.finding_id),
            "claimId": finding.claim_id,
            "criterionId": finding.criterion_id,
            "failureMode": finding.failure_mode,
            "quote": finding.quote,
            "locator": finding.locator,
        }
        if finding.quote is None:
            entry["quoteAbsentCause"] = QUOTE_ABSENT_CAUSE
        sections.append(entry)
    return sections


def _generator_level(
    instrument: InstrumentInfo,
    contents: list[ContentInfo],
    generators: dict[UUID, GeneratorInfo],
    current: dict[UUID, JudgmentInfo],
) -> list[dict[str, Any]]:
    """Per generator: for each claim, the distribution of status across the dataset.
    Contents with an unknown generator are EXCLUDED (they go to the caveat); a claim
    excluded by coverage stays out of the denominator (ADR-0011 clause 4)."""
    by_generator: dict[UUID, list[ContentInfo]] = {}
    for content in contents:
        if content.generator_version_id is not None:
            by_generator.setdefault(content.generator_version_id, []).append(content)

    sections: list[dict[str, Any]] = []
    for generator_id, members in sorted(by_generator.items(), key=lambda kv: str(kv[0])):
        generator = generators.get(generator_id)
        per_claim: list[dict[str, Any]] = []
        for claim in instrument.claims:
            distribution = {"supported": 0, "refuted": 0, "insufficient": 0}
            excluded = 0
            not_evaluated = 0
            for content in members:
                judgment = current.get(content.content_id)
                if judgment is None:
                    not_evaluated += 1
                    continue
                if claim.claim_id in judgment.coverage.get("excludedClaims", []):
                    excluded += 1
                    continue
                status = next(
                    (c.status for c in judgment.claims if c.claim_id == claim.claim_id), None
                )
                if status in distribution:
                    distribution[status] += 1
            evaluated = sum(distribution.values())
            per_claim.append(
                {
                    "claimId": claim.claim_id,
                    "statement": claim.statement,
                    "distribution": distribution,
                    "excludedNotApplicable": excluded,
                    "notEvaluated": not_evaluated,
                    # Coverage alongside every result (ADR-0011 clause 3).
                    "coverage": {"evaluated": evaluated, "of": len(members)},
                }
            )
        sections.append(
            {
                "generatorVersionId": str(generator_id),
                "name": generator.name if generator else None,
                "version": generator.version if generator else None,
                "contentsCounted": len(members),
                "perClaim": per_claim,
            }
        )
    return sections


def _caveats(
    contents: list[ContentInfo],
    briefs: dict[UUID, BriefInfo],
    capabilities: dict[str, CapabilityInfo | None],
    current: dict[UUID, JudgmentInfo],
) -> dict[str, Any]:
    """The canonical kinds (12-define invariant 4), every key always present."""
    insufficient = [
        {
            "contentId": str(judgment.content_id),
            "claimId": claim.claim_id,
            "cause": _insufficiency_cause(claim.evidence_basis),
        }
        for judgment in current.values()
        for claim in judgment.claims
        if claim.status == "insufficient"
    ]

    unknown_contents = [str(c.content_id) for c in contents if c.generator_version_id is None]

    unaccepted = []
    for package_format, capability in sorted(capabilities.items()):
        if capability is None:
            unaccepted.append({"packageFormat": package_format, "adapterVersion": None})
        elif not capability.accepted:
            unaccepted.append(
                {"packageFormat": package_format, "adapterVersion": capability.adapter_version}
            )

    brief_completeness = [
        {
            "briefId": str(brief.brief_id),
            "promptRecorded": bool(brief.fields.get("promptRecorded", False)),
            "origin": brief.fields.get("origin"),
        }
        for brief in sorted(briefs.values(), key=lambda b: str(b.brief_id))
        if not brief.fields.get("promptRecorded", False)
    ]

    without_judgment = [str(c.content_id) for c in contents if c.content_id not in current]

    execution_errors = [
        {"contentId": str(judgment.content_id), "count": count}
        for judgment in sorted(current.values(), key=lambda j: str(j.content_id))
        if (count := judgment.coverage.get("criteria", {}).get("executionError", 0)) > 0
    ]

    authors = assessors_used(current)

    return {
        "insufficientEvidence": insufficient,
        # Inert in the first increment (single automated assessor) — present on purpose.
        "unresolvedDisagreements": [],
        "mixedAssessors": {
            # Empty below two: one author is the normal case and needs no caveat, and a
            # study nothing judged has no author to name.
            "assessors": authors if len(authors) > 1 else [],
            # ADR-0042: the reader is told what the mixture costs, because nothing else in
            # the document can. Every distribution here pools courses judged by different
            # artifacts, and a criterion's states come from whichever one reached it last.
            "note": (
                "more than one assessor produced the judgments in this report — the "
                "distributions pool populations judged by different artifacts, so read "
                "them per assessor or re-evaluate the dataset with one"
            ),
        },
        "unknownExclusions": {
            "contentIds": unknown_contents,
            # Since ADR-0024 the state is declared, not an oversight, and it is repairable:
            # reports published before it keep their old wording, frozen.
            "note": (
                "generator declared unknown — excluded from generator-level accumulation; "
                "attributable later"
            ),
        },
        "unacceptedAdapters": unaccepted,
        "briefCompleteness": brief_completeness,
        "contentsWithoutJudgment": without_judgment,
        "executionErrors": {
            "perContent": execution_errors,
            # ADR-0037: an execution fact of this run, never a verdict about the content;
            # re-evaluating the content replaces it.
            "note": (
                "criteria this run could not judge (execution failure) — "
                "not the content's fault; re-evaluate to replace"
            ),
        },
        # Deferred non-silently until the first task variable exists (13-code §3.6).
        "taskVariablePatterns": {
            "status": "deferred",
            "reason": "no task variables declared in the first increment",
        },
    }


def compose_report(
    study: Study,
    contents: list[ContentInfo],
    briefs: dict[UUID, BriefInfo],
    generators: dict[UUID, GeneratorInfo],
    judgments: list[JudgmentInfo],
    findings: list[FindingInfo],
    capabilities: dict[str, CapabilityInfo | None],
    instrument: InstrumentInfo,
    published_at: datetime,
) -> dict[str, Any]:
    current = latest_judgments(judgments)
    used_ids = {j.judgment_id for j in current.values()}
    findings_by_content: dict[UUID, list[FindingInfo]] = {}
    for finding in findings:
        if finding.judgment_id in used_ids:
            findings_by_content.setdefault(finding.content_id, []).append(finding)

    content_sections: list[dict[str, Any]] = []
    for content in sorted(contents, key=lambda c: str(c.content_id)):
        judgment = current.get(content.content_id)
        section: dict[str, Any] = {
            "contentId": str(content.content_id),
            "externalId": content.external_id,
            "packageFormat": content.package_format,
            "briefId": str(content.brief_id) if content.brief_id else None,
            "generatorVersionId": (
                str(content.generator_version_id) if content.generator_version_id else None
            ),
        }
        if judgment is None:
            section["judgmentId"] = None
            section["assessor"] = None
        else:
            section.update(
                {
                    "judgmentId": str(judgment.judgment_id),
                    "assessor": _assessor_section(judgment.assessor),
                    "derivedAt": judgment.derived_at.isoformat(),
                    "coverage": judgment.coverage,
                    "claims": _claim_section(judgment),
                    "findings": _finding_section(findings_by_content.get(content.content_id, [])),
                }
            )
        content_sections.append(section)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "studyId": str(study.id),
        "purpose": study.purpose,
        "instrumentVersionId": study.instrument_version_id,
        "publishedAt": published_at.isoformat(),
        "publishedBy": str(study.published_by) if study.published_by else None,
        "dataset": {
            "size": len(contents),
            "briefIds": [str(b) for b in study.brief_ids],
            "contentIds": [str(c) for c in study.content_ids],
        },
        # The immutable record of exactly which judgments this report reflects — and, since
        # ADR-0042, of WHOSE. The ids pin the rows; this pins the artifacts, which is the
        # half that still means something once the store they were minted in is gone.
        "judgmentIdsUsed": {
            str(content_id): str(judgment.judgment_id)
            for content_id, judgment in sorted(current.items(), key=lambda kv: str(kv[0]))
        },
        "assessorsUsed": assessors_used(current),
        "contents": content_sections,
        "generatorLevel": _generator_level(instrument, contents, generators, current),
        "caveats": _caveats(contents, briefs, capabilities, current),
    }


def compose_preview(
    study: Study,
    contents: list[ContentInfo],
    briefs: dict[UUID, BriefInfo],
    generators: dict[UUID, GeneratorInfo],
    judgments: list[JudgmentInfo],
    findings: list[FindingInfo],
    capabilities: dict[str, CapabilityInfo | None],
    instrument: InstrumentInfo | None,
    composed_at: datetime,
) -> dict[str, Any]:
    """What publishing WOULD write, composed on read — so nobody publishes blind.

    It sits beside `compose_report` and calls it, because the guarantee worth having is
    that the two say the same thing: a preview that composed differently would not be a
    preview of anything. Three things distinguish it, and all three are said IN THE
    PAYLOAD rather than only here:

    * `documentKind` — the reader is told what they are holding.
    * `composedAt` instead of `publishedAt`. `compose_report` emits `publishedAt`
      unconditionally and the console renders it unguarded, so a preview filling it with
      the composition's clock would read "Published <now>" about a study nobody published,
      which is the exact misreading this resource exists to prevent. The key is REMOVED,
      not nulled: a null renders as the epoch, an absence renders as nothing.
    * `frozenRecord` — whether the immutable report already exists, because after
      publishing a recomposition may legitimately differ from it (the report reads the
      registry live, so a generator attributed later shows up here and never there).

    `instrument` is optional here where `compose_report` demands one: a study at
    `declared` or `prepared` gets the whole document with empty sections and its gaps
    named, never a partial one and never a refusal — readiness informs, it does not block.
    """
    gaps: list[dict[str, Any]] = []
    if study.instrument_version_id is None:
        gaps.append({"gap": "instrument_not_pinned"})
    if not study.content_ids:
        gaps.append({"gap": "dataset_not_composed"})
    if study.instrument_version_id is not None and instrument is None:
        # Distinct from "not pinned": a pinned version that cannot be read is a real fault.
        gaps.append({"gap": "instrument_not_found"})

    header: dict[str, Any] = {
        "documentKind": "preview",
        # Named for the act that produced it — a read, not the human act of publishing.
        "composedAt": composed_at.isoformat(),
        "frozenRecord": {"exists": study.published_at is not None, "note": PREVIEW_NOTE},
        "gaps": gaps,
    }

    if instrument is None:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "studyId": str(study.id),
            "purpose": study.purpose,
            "instrumentVersionId": study.instrument_version_id,
            "publishedBy": None,  # naturally absent: publishing is what sets it
            "dataset": {
                "size": len(contents),
                "briefIds": [str(b) for b in study.brief_ids],
                "contentIds": [str(c) for c in study.content_ids],
            },
            "judgmentIdsUsed": {},
            "assessorsUsed": [],
            "contents": [],
            "generatorLevel": [],
            # Every caveat kind, even here (12-define invariant 4): a consumer that walks
            # the kinds must read one shape at every status, or it learns to guess.
            "caveats": _caveats([], {}, {}, {}),
        } | header

    report = compose_report(
        study=study,
        contents=contents,
        briefs=briefs,
        generators=generators,
        judgments=judgments,
        findings=findings,
        capabilities=capabilities,
        instrument=instrument,
        # Passed only to be removed below. `compose_report`'s signature and output stay
        # untouched: what it writes is frozen jsonb, and being wrong inwards is unfixable.
        published_at=composed_at,
    )
    # `del` rather than `pop`: should `compose_report` ever stop emitting it, this must
    # fail loudly instead of quietly ceasing to protect.
    del report["publishedAt"]
    return report | header
