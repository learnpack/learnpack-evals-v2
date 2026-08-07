"""`BriefIntakePort` adapter: derive the brief from a LearnpackV1 package (ADR-0022).

Best-effort and non-blocking: any miss — no syllabus artifact, fetch failure, unparseable
content — logs and returns None, and the content registers with its brief absent (a
first-class recorded state). Registration never depends on this succeeding.
"""

import json
import logging
from typing import Any, Protocol

from app.modules.evaluand_registry.application.ports import DerivedBrief
from app.modules.evaluand_registry.infrastructure import acl_learnpack
from app.modules.evaluand_registry.infrastructure.fetchers import BriefIntakeError

logger = logging.getLogger(__name__)


class ArtifactFetcherPort(Protocol):
    def fetch(self, locator: str) -> bytes: ...


def _syllabus_locator(artifacts: list[dict[str, Any]]) -> str | None:
    for artifact in artifacts:
        locator = artifact.get("locator", "")
        if artifact.get("kind") == "syllabus" or locator.endswith(
            acl_learnpack.SYLLABUS_LOCATOR_SUFFIX
        ):
            return str(locator)
    return None


class LearnpackBriefIntake:
    def __init__(self, fetcher: ArtifactFetcherPort) -> None:
        self._fetcher = fetcher

    def derive(self, package_format: str, artifacts: list[dict[str, Any]]) -> DerivedBrief | None:
        if package_format != acl_learnpack.PACKAGE_FORMAT:
            return None
        locator = _syllabus_locator(artifacts)
        if locator is None:
            return None
        try:
            return acl_learnpack.derive_brief(self._fetcher.fetch(locator))
        except (BriefIntakeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("brief intake failed for '%s': %s — registered absent", locator, exc)
            return None
