"""Read side of Evaluation Studies + the composed queries (13-code §6).

Matching and readiness live here — the operational consumer — composed from other
modules' publics via the gateway ports. Both are pure over local DTOs. Readiness
**informs, it never blocks** (12-define invariant 1).
"""

from typing import Any
from uuid import UUID

from app.modules.evaluation_studies.application.dtos import (
    CapabilityInfo,
    InstrumentInfo,
    RatificationInfo,
    StudyDTO,
    StudyReportDTO,
)
from app.modules.evaluation_studies.application.ports import (
    StudyReportRepositoryPort,
    StudyRepositoryPort,
)
from app.modules.evaluation_studies.domain.model import Study


def _to_dto(study: Study) -> StudyDTO:
    return StudyDTO(
        study_id=study.id,
        name=study.name,
        description=study.description,
        status=study.status,
        instrument_version_id=study.instrument_version_id,
        assessor_id=study.assessor_id,
        brief_ids=study.brief_ids,
        content_ids=study.content_ids,
        created_at=study.created_at,
        opened_at=study.opened_at,
        signed_off_at=study.signed_off_at,
        signed_off_by=study.signed_off_by,
    )


def get_study(studies: StudyRepositoryPort, study_id: UUID) -> StudyDTO | None:
    study = studies.get_by_id(study_id)
    return None if study is None else _to_dto(study)


def list_studies(studies: StudyRepositoryPort) -> list[StudyDTO]:
    return [_to_dto(study) for study in studies.list_all()]


def get_report(reports: StudyReportRepositoryPort, study_id: UUID) -> StudyReportDTO | None:
    return reports.get(study_id)


# ------------------------------------------------------------------------ matching (§6)


def compute_matching(
    instrument: InstrumentInfo, capability: CapabilityInfo | None, package_format: str
) -> dict[str, Any]:
    """Demand (`required_data` of the instrument) × supply (`get_capabilities`) →
    expected coverage + unmet demand. Where ADR-0017's systemic gap surfaces: 'this
    format does not declare objectives' is reported here once, not per course."""
    supplied = set(capability.capabilities) if capability else set()

    criteria_sections: list[dict[str, Any]] = []
    unmet: dict[str, list[str]] = {}
    covered_by_claim: dict[str, dict[str, int]] = {}
    for criterion in instrument.criteria:
        missing = [d for d in criterion.required_data if d not in supplied]
        covered = not missing
        criteria_sections.append(
            {
                "criterionId": criterion.criterion_id,
                "requiredData": list(criterion.required_data),
                "missingData": missing,
                "covered": covered,
                "onMissingEvidence": criterion.on_missing_evidence,
            }
        )
        for datum in missing:
            unmet.setdefault(datum, []).append(criterion.criterion_id)
        for claim_id in criterion.claim_ids:
            entry = covered_by_claim.setdefault(claim_id, {"criteria": 0, "covered": 0})
            entry["criteria"] += 1
            entry["covered"] += covered

    return {
        "instrumentVersionId": instrument.instrument_version_id,
        "packageFormat": package_format,
        "adapterVersion": capability.adapter_version if capability else None,
        "extractionAccepted": capability.accepted if capability else None,
        "criteria": criteria_sections,
        "unmetDemand": [
            {"dataRequirementId": datum, "criterionIds": criterion_ids}
            for datum, criterion_ids in sorted(unmet.items())
        ],
        "claims": [
            {
                "claimId": claim.claim_id,
                "criteria": covered_by_claim.get(claim.claim_id, {"criteria": 0})["criteria"],
                "coveredCriteria": covered_by_claim.get(claim.claim_id, {"covered": 0})["covered"],
            }
            for claim in instrument.claims
        ],
    }


# ------------------------------------------------------------------------ readiness (§6)


def compute_readiness(
    study: Study,
    instrument: InstrumentInfo | None,
    capabilities: dict[str, CapabilityInfo | None],
    ratifications: list[RatificationInfo],
    dataset_formats: list[str],
) -> dict[str, Any]:
    """Gaps PER CLAIM ('claim without criteria' · 'criterion without a datum in this
    format' · 'extraction not accepted') plus the study-level gaps — including 'no
    ratified assessor' (ADR-0019). It informs, it does not block."""
    study_gaps: list[dict[str, Any]] = []
    if study.instrument_version_id is None:
        study_gaps.append({"gap": "instrument_not_pinned"})
    if study.assessor_id is None:
        # Distinct from `no_ratified_assessor` below: that one says nobody COULD judge with
        # this norm, this one says nobody has been named to (ADR-0042 §8). A study that
        # predates the pin carries it for good, and it is why its reads are unfiltered.
        study_gaps.append({"gap": "assessor_not_pinned"})
    if not study.content_ids:
        study_gaps.append({"gap": "dataset_not_composed"})
    if study.instrument_version_id is not None and not ratifications:
        study_gaps.append(
            {
                "gap": "no_ratified_assessor",
                "instrumentVersionId": study.instrument_version_id,
            }
        )

    format_sections: list[dict[str, Any]] = []
    for package_format in sorted(set(dataset_formats)):
        capability = capabilities.get(package_format)
        format_sections.append(
            {
                "packageFormat": package_format,
                "adapterVersion": capability.adapter_version if capability else None,
                "extractionAccepted": capability.accepted if capability else None,
            }
        )

    claim_sections: list[dict[str, Any]] = []
    if instrument is not None:
        criteria_by_claim: dict[str, list[Any]] = {}
        for criterion in instrument.criteria:
            for claim_id in criterion.claim_ids:
                criteria_by_claim.setdefault(claim_id, []).append(criterion)

        for claim in instrument.claims:
            gaps: list[dict[str, Any]] = []
            criteria = criteria_by_claim.get(claim.claim_id, [])
            if not criteria:
                gaps.append({"gap": "claim_without_criteria"})
            for package_format in sorted(set(dataset_formats)):
                capability = capabilities.get(package_format)
                supplied = set(capability.capabilities) if capability else set()
                for criterion in criteria:
                    missing = [d for d in criterion.required_data if d not in supplied]
                    if missing:
                        gaps.append(
                            {
                                "gap": "criterion_without_datum_in_format",
                                "criterionId": criterion.criterion_id,
                                "packageFormat": package_format,
                                "missingData": missing,
                            }
                        )
                if capability is not None and not capability.accepted:
                    gaps.append({"gap": "extraction_not_accepted", "packageFormat": package_format})
            claim_sections.append({"claimId": claim.claim_id, "gaps": gaps})

    return {
        "studyId": str(study.id),
        "status": study.status,
        "informative": True,  # readiness informs, it never blocks
        "studyGaps": study_gaps,
        "formats": format_sections,
        "claims": claim_sections,
    }
