"""GenerationBrief — the generation assignment (GLOSSARY, design 12 §Registry).

Immutable, with its own identity: content versions reference a `briefId`, which is the
key of paired design between generator versions (same briefs, new products). Lean on
purpose: free text plus only the typed fields that task variables end up consuming
(demand-driven). An absent brief is recorded as absent — it limits paired comparison
and leaves alternative explanations standing.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


class InvalidBrief(Exception):
    """The brief violates a domain invariant."""


@dataclass(frozen=True)
class GenerationBrief:
    id: UUID
    brief: str
    fields: dict[str, Any] = field(default_factory=dict)
    # Identity of the effective instruction (ADR-0022): mechanically derived briefs carry
    # sha256(description + materialsHash); manually registered briefs carry none.
    brief_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.brief.strip():
            raise InvalidBrief("brief is required")
