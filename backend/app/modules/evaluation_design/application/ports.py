"""Ports required by Rubric Authoring. Implemented in infrastructure."""

from typing import Protocol

from app.modules.evaluation_design.application.dtos import RubricSnapshot


class RubricRepositoryPort(Protocol):
    def get_snapshot(self, rubric_version_id: str) -> RubricSnapshot | None: ...
