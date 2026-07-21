"""Ports required by Rubric Authoring. Implemented in infrastructure."""

from typing import Protocol

from app.modules.rubric_authoring.application.dtos import RubricSnapshot


class RubricRepositoryPort(Protocol):
    def get_snapshot(self, rubric_version_id: str) -> RubricSnapshot | None: ...
