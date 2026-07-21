"""Identity's Published Language.

`AssessorDTO` is the only thing other modules ever see — they never import
`identity.domain` (ARCHITECTURE.md §3).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AssessorDTO:
    assessor_id: UUID
    role: str
    email: str | None = None
    display_name: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
