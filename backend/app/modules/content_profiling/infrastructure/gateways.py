"""Gateways over other modules' public surfaces (the only imports allowed to cross).

They translate foreign DTOs into this module's own shapes at the boundary, so the
application layer stays free of foreign types (ARCHITECTURE.md §3).
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.content_profiling.application.dtos import ArtifactDTO, PackageDTO
from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.modules.evaluation_design.public import InstrumentQueries


class RegistryContentGateway:
    """`ContentGatewayPort` over the Evaluand Registry: package + declared metadata."""

    def __init__(self, session: Session) -> None:
        self._queries = EvaluandRegistryQueries(session)

    def get_package(self, content_id: UUID) -> PackageDTO | None:
        package = self._queries.get_content_package(content_id)
        if package is None:
            return None
        return PackageDTO(
            content_id=package.content_id,
            package_format=package.package_format,
            artifacts=tuple(
                ArtifactDTO(kind=a.kind, locator=a.locator, format=a.format)
                for a in package.artifacts
            ),
        )

    def list_content_ids(self, package_format: str) -> list[UUID]:
        return [
            snapshot.content_id
            for snapshot in self._queries.list_content_snapshots()
            if snapshot.package_format == package_format
        ]


class DesignNamespaceGateway:
    """`DataRequirementNamespacePort` over Evaluation Design (Conformist, ADR-0014)."""

    def __init__(self, session: Session) -> None:
        self._queries = InstrumentQueries(session)

    def value_domains(self) -> Mapping[str, dict[str, Any]]:
        return {r.id: r.value_domain for r in self._queries.get_data_requirements()}
