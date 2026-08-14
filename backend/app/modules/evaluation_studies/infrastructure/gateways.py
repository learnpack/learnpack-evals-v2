"""Gateways: the only place Evaluation Studies imports other modules' publics.

Each gateway fills a local port with a foreign `public.py` behind it, translating the
published language into this module's `*Info` types (architecture rule 3 — the
application layer never crosses the module boundary itself).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.content_profiling.public import ContentProfilingQueries
from app.modules.evaluand_registry.public import ContentSnapshot, EvaluandRegistryQueries
from app.modules.evaluation.public import EvaluationQueries
from app.modules.evaluation_design.public import InstrumentQueries
from app.modules.evaluation_studies.application.dtos import (
    AssessorInfo,
    BriefInfo,
    CapabilityInfo,
    ClaimJudgment,
    ContentInfo,
    CriterionOutcomeInfo,
    FindingInfo,
    GeneratorInfo,
    InstrumentClaim,
    InstrumentCriterion,
    InstrumentInfo,
    JudgmentInfo,
    RatificationInfo,
)
from app.modules.identity.public import AssessorDTO, IdentityQueries


def _assessor_info(assessor_id: UUID, dto: AssessorDTO | None) -> AssessorInfo:
    """The author of a judgment, named where Identity can name it.

    An id with no row answers with the id alone rather than with nothing: the judgment
    exists and its author is recorded — losing the provenance because a label could not be
    fetched would be the exact failure this whole change exists to end.
    """
    automated = dto.automated if dto is not None else None
    if automated is None:
        return AssessorInfo(assessor_id=assessor_id)
    return AssessorInfo(assessor_id=assessor_id, name=automated.name, version=automated.version)


class RegistryGateway:
    """`RegistryGatewayPort`: the evaluand side, translated to local types."""

    def __init__(self, session: Session) -> None:
        self._queries = EvaluandRegistryQueries(session)

    @staticmethod
    def _to_info(snapshot: ContentSnapshot) -> ContentInfo:
        return ContentInfo(
            content_id=snapshot.content_id,
            external_id=snapshot.external_id,
            package_format=snapshot.package_format,
            brief_id=snapshot.brief_id,
            generator_version_id=snapshot.generator_version_id,
        )

    def get_contents_by_briefs(self, brief_ids: list[UUID]) -> list[ContentInfo]:
        snapshots = self._queries.get_available_contents(brief_ids=brief_ids)
        return [self._to_info(s) for s in snapshots]

    def get_contents_by_ids(self, content_ids: list[UUID]) -> list[ContentInfo]:
        wanted = set(content_ids)
        return [
            self._to_info(s)
            for s in self._queries.list_content_snapshots()
            if s.content_id in wanted
        ]

    def get_brief(self, brief_id: UUID) -> BriefInfo | None:
        dto = self._queries.get_brief(brief_id)
        if dto is None:
            return None
        return BriefInfo(
            brief_id=dto.brief_id,
            brief=dto.brief,
            fields=dto.fields,
            brief_hash=dto.brief_hash,
        )

    def get_generator(self, generator_version_id: UUID) -> GeneratorInfo | None:
        dto = self._queries.get_generator_version(generator_version_id)
        if dto is None:
            return None
        return GeneratorInfo(
            generator_version_id=dto.generator_version_id, name=dto.name, version=dto.version
        )


class EvaluationGateway:
    """`EvaluationGatewayPort`: judgments/findings/ratifications, translated.

    It crosses to TWO modules, and that is what a gateway is for. Evaluation says which
    assessor produced a judgment; Identity says what that assessor is called. Neither
    module has to learn the other's vocabulary, and the join that used to be impossible
    from the application layer happens here, where crossing is legal (ARCHITECTURE §3).
    """

    def __init__(self, session: Session) -> None:
        self._queries = EvaluationQueries(session)
        self._identities = IdentityQueries(session)

    def get_judgments(
        self,
        content_ids: list[UUID],
        instrument_version_id: str,
        assessor_id: UUID | None = None,
    ) -> list[JudgmentInfo]:
        dtos = self._queries.get_judgments(content_ids, instrument_version_id, assessor_id)
        # One batched lookup for the whole set, whatever its size (ADR-0006): a study of
        # twenty courses has at most a handful of distinct authors.
        assessors = self._identities.list_assessors(sorted({dto.assessor_id for dto in dtos}))
        return [
            JudgmentInfo(
                judgment_id=dto.judgment_id,
                content_id=dto.content_id,
                derived_at=dto.derived_at,
                coverage=dto.coverage,
                claims=tuple(
                    ClaimJudgment(
                        claim_id=claim.claim_id,
                        status=claim.status,
                        evidence_basis=claim.evidence_basis,
                    )
                    for claim in dto.claims
                ),
                assessor=_assessor_info(dto.assessor_id, assessors.get(dto.assessor_id)),
            )
            for dto in dtos
        ]

    def get_findings(
        self,
        content_ids: list[UUID],
        instrument_version_id: str,
        assessor_id: UUID | None = None,
    ) -> list[FindingInfo]:
        return [
            FindingInfo(
                finding_id=dto.finding_id,
                judgment_id=dto.judgment_id,
                content_id=dto.content_id,
                claim_id=dto.claim_id,
                criterion_id=dto.criterion_id,
                failure_mode=dto.failure_mode,
                quote=dto.quote,
                locator=dto.locator,
            )
            for dto in self._queries.get_findings(content_ids, instrument_version_id, assessor_id)
        ]

    def get_criterion_outcomes(
        self,
        content_ids: list[UUID],
        instrument_version_id: str,
        assessor_id: UUID | None = None,
    ) -> list[CriterionOutcomeInfo]:
        return [
            CriterionOutcomeInfo(
                judgment_id=dto.judgment_id,
                content_id=dto.content_id,
                criterion_id=dto.criterion_id,
                outcome=dto.outcome,
                derived=dto.derived,
                quote=dto.quote,
                locator=dto.locator,
                failure_mode=dto.failure_mode,
                comment=dto.comment,
                execution_cause=dto.execution_cause,
            )
            for dto in self._queries.get_criterion_outcomes(
                content_ids, instrument_version_id, assessor_id
            )
        ]

    def list_ratifications(self, instrument_version_id: str) -> list[RatificationInfo]:
        return [
            RatificationInfo(
                assessor_id=dto.assessor_id,
                instrument_version_id=dto.instrument_version_id,
            )
            for dto in self._queries.list_ratifications(instrument_version_id)
        ]


class DesignGateway:
    """`DesignGatewayPort`: the pinned norm, translated to local specs."""

    def __init__(self, session: Session) -> None:
        self._queries = InstrumentQueries(session)

    def get_instrument(self, instrument_version_id: str) -> InstrumentInfo | None:
        snapshot = self._queries.get_instrument(instrument_version_id)
        if snapshot is None:
            return None
        return InstrumentInfo(
            instrument_version_id=snapshot.instrument_version_id,
            status=snapshot.status,
            claims=tuple(
                InstrumentClaim(
                    claim_id=c.claim_id,
                    statement=c.statement,
                    quality_ids=tuple(c.quality_ids),
                )
                for c in snapshot.claims
            ),
            criteria=tuple(
                InstrumentCriterion(
                    criterion_id=c.criterion_id,
                    claim_ids=tuple(c.claim_ids),
                    required_data=tuple(c.required_data),
                    on_missing_evidence=c.on_missing_evidence,
                )
                for c in snapshot.criteria
            ),
            quality_dimensions=dict(snapshot.quality_dimensions),
        )


class ProfilingGateway:
    """`ProfilingGatewayPort`: the supply side of the matching, translated."""

    def __init__(self, session: Session) -> None:
        self._queries = ContentProfilingQueries(session)

    def get_capabilities(self, package_format: str) -> CapabilityInfo | None:
        snapshot = self._queries.get_capabilities(package_format)
        if snapshot is None:
            return None
        return CapabilityInfo(
            package_format=snapshot.package_format,
            adapter_version=snapshot.adapter_version,
            capabilities=tuple(snapshot.capabilities),
            accepted=snapshot.accepted,
        )
