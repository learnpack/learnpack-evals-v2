"""Domain events published by Evaluation Design (design 10 §events).

`InstrumentVersionPublished` carries the full snapshot (11-connect): subscribers get a
self-contained instrument without querying back. Draft-edit events are a deliberate
first-increment omission (13-code-qa) — the publication event is enough.
"""

from typing import Any

from app.modules.evaluation_design.domain.instrument import InstrumentVersion
from app.shared.domain.events import DomainEvent

AGGREGATE_TYPE = "InstrumentVersion"


def snapshot_payload(instrument: InstrumentVersion) -> dict[str, Any]:
    """The published-language shape of an instrument version (camelCase, plain data)."""
    return {
        "instrumentVersionId": instrument.id,
        "instrumentId": instrument.instrument_id,
        "version": instrument.version,
        "name": instrument.name,
        "purpose": instrument.purpose,
        "status": instrument.status,
        "claims": [
            {
                "claimId": c.claim_id,
                "statement": c.statement,
                "qualityIds": list(c.quality_ids),
                "warrants": list(c.warrants),
                "alternativeExplanations": list(c.alternative_explanations),
                "sufficiency": {"rule": c.sufficiency.rule},
            }
            for c in instrument.claims
        ],
        "criteria": [
            {
                "criterionId": c.criterion_id,
                "statement": c.statement,
                "passCondition": c.pass_condition,
                "failureModes": list(c.failure_modes),
                "claimIds": list(c.claim_ids),
                "requiredData": list(c.required_data),
                "onMissingEvidence": c.on_missing_evidence,
                "eligibleSources": list(c.eligible_sources),
                "condition": c.condition,
            }
            for c in instrument.criteria
        ],
        "bindings": [
            {"packageFormat": b.package_format, "taskVariables": b.task_variables}
            for b in instrument.bindings
        ],
    }


def instrument_version_published(instrument: InstrumentVersion) -> DomainEvent:
    return DomainEvent(
        event_type="InstrumentVersionPublished",
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=instrument.id,
        payload=snapshot_payload(instrument),
    )
