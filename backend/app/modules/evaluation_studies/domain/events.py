"""Domain events of Evaluation Studies (13-code §3.6/§5).

**Choosing publishes nothing** — not the instrument, not the judge, not the dataset. All
three evolve freely while the study is a draft, and the act worth recording is the one
that makes them binding: `StudyOpened` carries the whole triple (ADR-0043 §2). Two events
were retired with that decision, `InstrumentPinned` and `AssessorPinned`; rows already in
the outbox stay and are read as the record of what happened.
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
        payload={
            "studyId": str(study.id),
            "name": study.name,
            "description": study.description,
        },
    )


def study_opened(study: Study) -> DomainEvent:
    return DomainEvent(
        event_type="StudyOpened",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={
            "studyId": str(study.id),
            # Opening IS the pin, so this event is where the triple becomes a fact.
            "instrumentVersionId": study.instrument_version_id,
            "assessorId": str(study.assessor_id),
            "briefIds": [str(b) for b in study.brief_ids],
            "contentIds": [str(c) for c in study.content_ids],
        },
    )


def study_signed_off(study: Study, judgment_ids: list[UUID]) -> DomainEvent:
    return DomainEvent(
        event_type="StudySignedOff",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=str(study.id),
        payload={
            "studyId": str(study.id),
            "instrumentVersionId": study.instrument_version_id,
            "signedOffBy": str(study.signed_off_by),
            "judgmentIdsUsed": [str(j) for j in judgment_ids],
        },
    )
