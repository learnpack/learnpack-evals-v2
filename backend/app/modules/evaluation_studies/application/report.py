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
    BriefInfo,
    CapabilityInfo,
    ContentInfo,
    FindingInfo,
    GeneratorInfo,
    InstrumentInfo,
    JudgmentInfo,
)
from app.modules.evaluation_studies.domain.model import Study

SCHEMA_VERSION = 1

# ADR-0021: the fail derived from absence carries no quote; the report must show its cause
# so it is not read as an incomplete finding.
QUOTE_ABSENT_CAUSE = "required data absent"


def latest_judgments(judgments: list[JudgmentInfo]) -> dict[UUID, JudgmentInfo]:
    """Judgments are append-only; the most recent per content is the current one."""
    current: dict[UUID, JudgmentInfo] = {}
    for judgment in sorted(judgments, key=lambda j: (j.derived_at, str(j.judgment_id))):
        current[judgment.content_id] = judgment
    return current


def _insufficiency_cause(evidence_basis: dict[str, int]) -> str:
    """Qualify an `insufficient` by its cause (ADR-0018: three causes, three remedies)."""
    no_evidence = evidence_basis.get("noEvidence", 0) > 0
    not_assessed = evidence_basis.get("notAssessed", 0) > 0
    if no_evidence and not_assessed:
        return "mixed"
    if no_evidence:
        return "no_evidence"
    if not_assessed:
        return "not_assessed"
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

    return {
        "insufficientEvidence": insufficient,
        # Inert in the first increment (single automated assessor) — present on purpose.
        "unresolvedDisagreements": [],
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
        else:
            section.update(
                {
                    "judgmentId": str(judgment.judgment_id),
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
        # The immutable record of exactly which judgments this report reflects.
        "judgmentIdsUsed": {
            str(content_id): str(judgment.judgment_id)
            for content_id, judgment in sorted(current.items(), key=lambda kv: str(kv[0]))
        },
        "contents": content_sections,
        "generatorLevel": _generator_level(instrument, contents, generators, current),
        "caveats": _caveats(contents, briefs, capabilities, current),
    }
