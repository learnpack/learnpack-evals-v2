"""Domain events of Evaluation Studies (13-code §3.6/§5).

`ComposeDataset` publishes nothing: the recipe evolves freely until `open` fixes it —
the three lifecycle acts and the publication are the record.
"""

from uuid import UUID

from app.modules.evaluation_studies.domain.model import Study
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "EvaluationStudy"


def study_declared(study: Study) -> DomainEvent:
    return DomainEvent(
        event_type="StudyDeclared",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={"studyId": str(study.id), "purpose": study.purpose},
    )


def instrument_pinned(study: Study) -> DomainEvent:
    return DomainEvent(
        event_type="InstrumentPinned",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={
            "studyId": str(study.id),
            "instrumentVersionId": study.instrument_version_id,
        },
    )


def assessor_pinned(study: Study) -> DomainEvent:
    return DomainEvent(
        event_type="AssessorPinned",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={
            "studyId": str(study.id),
            "assessorId": str(study.assessor_id),
        },
    )


def study_opened(study: Study) -> DomainEvent:
    return DomainEvent(
        event_type="StudyOpened",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={
            "studyId": str(study.id),
            "instrumentVersionId": study.instrument_version_id,
            # Opening fixes the whole triple now, so the event that records the act says so.
            "assessorId": str(study.assessor_id),
            "briefIds": [str(b) for b in study.brief_ids],
            "contentIds": [str(c) for c in study.content_ids],
        },
    )


def study_published(study: Study, judgment_ids: list[UUID]) -> DomainEvent:
    return DomainEvent(
        event_type="StudyPublished",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={
            "studyId": str(study.id),
            "instrumentVersionId": study.instrument_version_id,
            "publishedBy": str(study.published_by),
            "judgmentIdsUsed": [str(j) for j in judgment_ids],
        },
    )
