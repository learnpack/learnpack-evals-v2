"""`BriefIntakePort` adapters: derive the brief from the package (ADR-0022).

Mirrors profiling's adapter registry (design 13 §3.4): one intake per `PackageFormat`,
registered in `BRIEF_INTAKES_BY_FORMAT`; `PackageBriefIntake` dispatches by format. A new
format (LearnpackV2 with native briefs is expected) is a new entry here — never a change
to the registry's model or wiring.

Best-effort and non-blocking: any miss — unsupported format, no syllabus artifact, fetch
failure, unparseable content — logs and returns None, and the content registers with its
brief absent (a first-class recorded state). Registration never depends on this
succeeding.
"""

import json
import logging
from collections.abc import Mapping
from typing import Any, Protocol

from app.modules.evaluand_registry.application.ports import DerivedBrief
from app.modules.evaluand_registry.infrastructure import acl_learnpack
from app.shared.infrastructure.fetchers import FetchError

logger = logging.getLogger(__name__)


class ArtifactFetcherPort(Protocol):
    def fetch(self, locator: str) -> bytes: ...


class FormatBriefIntakePort(Protocol):
    """What one format contributes: where its commission lives, and how to read it."""

    package_format: str

    def locate(self, artifacts: list[dict[str, Any]]) -> str | None: ...

    def derive(self, payload: bytes) -> DerivedBrief | None: ...


class LearnpackV1BriefIntake:
    """LearnpackV1: the commission is `.learn/initialSyllabus.json` (ADR-0022)."""

    package_format = acl_learnpack.PACKAGE_FORMAT

    def locate(self, artifacts: list[dict[str, Any]]) -> str | None:
        for artifact in artifacts:
            locator = artifact.get("locator", "")
            if artifact.get("kind") == "syllabus" or locator.endswith(
                acl_learnpack.SYLLABUS_LOCATOR_SUFFIX
            ):
                return str(locator)
        return None

    def derive(self, payload: bytes) -> DerivedBrief | None:
        return acl_learnpack.derive_brief(payload)


BRIEF_INTAKES_BY_FORMAT: dict[str, FormatBriefIntakePort] = {
    intake.package_format: intake for intake in (LearnpackV1BriefIntake(),)
}


class PackageBriefIntake:
    """`BriefIntakePort`: dispatch to the format's intake, if one exists."""

    def __init__(
        self,
        fetcher: ArtifactFetcherPort,
        intakes: Mapping[str, FormatBriefIntakePort] = BRIEF_INTAKES_BY_FORMAT,
    ) -> None:
        self._fetcher = fetcher
        self._intakes = intakes

    def derive(self, package_format: str, artifacts: list[dict[str, Any]]) -> DerivedBrief | None:
        intake = self._intakes.get(package_format)
        if intake is None:
            return None  # no intake for this format: registered absent, not an error
        locator = intake.locate(artifacts)
        if locator is None:
            return None
        try:
            return intake.derive(self._fetcher.fetch(locator))
        except (FetchError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("brief intake failed for '%s': %s — registered absent", locator, exc)
            return None
