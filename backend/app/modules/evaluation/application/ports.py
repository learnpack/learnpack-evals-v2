"""Ports required by Evaluation's use cases."""

from typing import Protocol
from uuid import UUID

from app.modules.evaluation.application.dtos import EvaluationDTO
from app.modules.evaluation.domain.evaluation import Evaluation


class EvaluationRepositoryPort(Protocol):
    def add(self, evaluation: Evaluation) -> None: ...

    def list_for_contents(self, content_ids: list[UUID]) -> list[EvaluationDTO]:
        """Batch read: every evaluation of those contents, scores included.

        Batch on purpose — Reporting would otherwise issue one query per content (ADR-0006).
        """
        ...
