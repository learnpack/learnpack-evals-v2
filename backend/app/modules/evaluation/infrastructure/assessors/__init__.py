"""Registry of automated assessor packages (in code, like `ADAPTERS_BY_FORMAT`).

Each package is a versioned software artifact (ADR-0016): its (name, version) is its
identity, its coverage over the instrument lineage is declared here, and the CLI
`ratify-assessor` upserts it as an `assessors` row and records the ratification act
(ADR-0019). Adding an entry is adding an assessor; changing one is a new version.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.evaluation.domain.derivation import Executor
from app.modules.evaluation.domain.model import Coverage
from app.modules.evaluation.infrastructure.assessors import (
    drafts_hybrid,
    drafts_structural,
    structural,
)


@dataclass(frozen=True)
class AssessorPackage:
    name: str
    version: str
    instrument_id: str
    executors: Mapping[str, Executor]
    coverage: Coverage
    source_config: dict[str, Any]
    # Drops whatever the package memoized across evaluations, if it memoizes anything.
    # Not identity and not in `source_config`: what a package remembers between runs
    # changes what it SPENDS, never what it answers — and a run that reuses last run's
    # answers reports a spend it did not make and leaves an empty trace.
    reset_caches: Callable[[], None] | None = None

    @property
    def display_name(self) -> str:
        return f"{self.name} v{self.version}"


AUTOMATED_ASSESSORS: dict[tuple[str, str], AssessorPackage] = {
    (package.name, package.version): package
    for package in (
        AssessorPackage(
            name=structural.NAME,
            version=structural.VERSION,
            instrument_id=structural.INSTRUMENT_ID,
            executors=structural.EXECUTORS,
            coverage=structural.COVERAGE,
            source_config=structural.SOURCE_CONFIG,
        ),
        AssessorPackage(
            name=drafts_structural.NAME,
            version=drafts_structural.VERSION,
            instrument_id=drafts_structural.INSTRUMENT_ID,
            executors=drafts_structural.EXECUTORS,
            coverage=drafts_structural.COVERAGE,
            source_config=drafts_structural.SOURCE_CONFIG,
        ),
        AssessorPackage(
            name=drafts_hybrid.NAME,
            version=drafts_hybrid.VERSION,
            instrument_id=drafts_hybrid.INSTRUMENT_ID,
            executors=drafts_hybrid.EXECUTORS,
            coverage=drafts_hybrid.COVERAGE,
            source_config=drafts_hybrid.SOURCE_CONFIG,
            reset_caches=drafts_hybrid.tasks.clear_task_cache,
        ),
    )
}
