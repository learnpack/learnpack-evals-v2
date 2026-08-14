"""The I/O of the report path, in one place — read through this module's own ports.

`compose_report` is pure and `queries.py` is pure by contract; something has to do the
reading, and it has to be callable from BOTH `PublishStudy` (which materializes the frozen
document) and the preview (which shows what that document would say). That rules out the
router: an application layer may not import infrastructure, so a gathering that lives there
is a gathering `PublishStudy` cannot use — which is how the same six statements came to be
written three times over (the router's fitness endpoint, the CLI's, and the test suite's).

Nothing foreign is imported here: the ports are this module's own Protocols, and the
gateways behind them do the crossing (ARCHITECTURE.md §3).
"""

from dataclasses import dataclass
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
from app.modules.evaluation_studies.application.ports import (
    DesignGatewayPort,
    EvaluationGatewayPort,
    ProfilingGatewayPort,
    RegistryGatewayPort,
)
from app.modules.evaluation_studies.domain.model import Study


@dataclass(frozen=True)
class ReportInputs:
    """Exactly what the report is composed from, minus the study and the clock."""

    instrument: InstrumentInfo | None
    contents: list[ContentInfo]
    briefs: dict[UUID, BriefInfo]
    generators: dict[UUID, GeneratorInfo]
    judgments: list[JudgmentInfo]
    findings: list[FindingInfo]
    capabilities: dict[str, CapabilityInfo | None]


def gather_report_inputs(
    study: Study,
    registry: RegistryGatewayPort,
    evaluation: EvaluationGatewayPort,
    design: DesignGatewayPort,
    profiling: ProfilingGatewayPort,
) -> ReportInputs:
    """Read every input the report is composed from, at ANY status.

    `instrument` comes back as `None` rather than raising, and the judgment and finding
    reads are skipped when nothing is pinned: at `declared` or `prepared` there may be no
    pin at all, and whether that absence is a fault is the CALLER's question — publishing
    refuses over it, a preview reports it as a gap and answers anyway. None-ness is a
    return type here, not an exception, the same way the fitness projection takes one.

    The briefs are the ones the CONTENTS reference, deliberately NOT the recipe union the
    fitness projection uses (ADR-0039 §3): `caveats.briefCompleteness` is computed from
    this dict and is frozen into published reports, so widening it here would silently
    change what publishing writes.
    """
    version_id = study.instrument_version_id
    instrument = design.get_instrument(version_id) if version_id is not None else None

    content_ids = list(study.content_ids)
    contents = registry.get_contents_by_ids(content_ids)

    briefs: dict[UUID, BriefInfo] = {}
    for brief_id in {c.brief_id for c in contents if c.brief_id is not None}:
        brief = registry.get_brief(brief_id)
        if brief is not None:
            briefs[brief_id] = brief

    generators: dict[UUID, GeneratorInfo] = {}
    for generator_id in {
        c.generator_version_id for c in contents if c.generator_version_id is not None
    }:
        generator = registry.get_generator(generator_id)
        if generator is not None:
            generators[generator_id] = generator

    capabilities: dict[str, CapabilityInfo | None] = {
        package_format: profiling.get_capabilities(package_format)
        for package_format in {c.package_format for c in contents}
    }

    return ReportInputs(
        instrument=instrument,
        contents=contents,
        briefs=briefs,
        generators=generators,
        judgments=(
            evaluation.get_judgments(content_ids, version_id) if version_id is not None else []
        ),
        findings=(
            evaluation.get_findings(content_ids, version_id) if version_id is not None else []
        ),
        capabilities=capabilities,
    )
