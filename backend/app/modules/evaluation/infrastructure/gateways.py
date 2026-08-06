"""Gateways to foreign publics — evaluation's ACL at the module boundary.

They translate foreign DTOs into this module's own domain types at the boundary, so the
application layer stays free of foreign types (ARCHITECTURE.md §3; the pattern of
content_profiling/infrastructure/gateways.py).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.content_profiling.public import ContentProfilingQueries
from app.modules.evaluation.domain.model import (
    BindingSpec,
    ClaimSpec,
    CriterionSpec,
    InstrumentSpec,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation_design.public import InstrumentQueries


class DesignInstrumentGateway:
    """`InstrumentGatewayPort`: the pinned norm, translated to local specs."""

    def __init__(self, session: Session) -> None:
        self._queries = InstrumentQueries(session)

    def get_instrument(self, instrument_version_id: str) -> InstrumentSpec | None:
        snapshot = self._queries.get_instrument(instrument_version_id)
        if snapshot is None:
            return None
        return InstrumentSpec(
            instrument_version_id=snapshot.instrument_version_id,
            instrument_id=snapshot.instrument_id,
            status=snapshot.status,
            claims=tuple(
                ClaimSpec(claim_id=c.claim_id, sufficiency_rule=c.sufficiency_rule)
                for c in snapshot.claims
            ),
            criteria=tuple(
                CriterionSpec(
                    criterion_id=c.criterion_id,
                    pass_condition=c.pass_condition,
                    failure_modes=tuple(c.failure_modes),
                    claim_ids=tuple(c.claim_ids),
                    required_data=tuple(c.required_data),
                    on_missing_evidence=c.on_missing_evidence,
                    condition=c.condition,
                )
                for c in snapshot.criteria
            ),
            bindings=tuple(
                BindingSpec(package_format=b.package_format, task_variables=b.task_variables)
                for b in snapshot.bindings
            ),
        )


class ProfilingGateway:
    """`ProfileGatewayPort`: the content's most recent `ok` profile, or None."""

    def __init__(self, session: Session) -> None:
        self._queries = ContentProfilingQueries(session)

    def get_profile(self, content_id: UUID) -> ProfileData | None:
        snapshot = self._queries.get_profile(content_id)
        if snapshot is None or snapshot.status != "ok":
            return None
        return ProfileData(
            profile_id=snapshot.profile_id,
            package_format=snapshot.package_format,
            entries={
                entry.data_requirement_id: ProfileEntryData(
                    data_requirement_id=entry.data_requirement_id,
                    provenance=entry.provenance,
                    value=entry.value,
                    quote=entry.quote,
                    locator=entry.locator,
                )
                for entry in snapshot.entries
            },
        )
