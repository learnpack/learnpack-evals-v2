"""DataRequirement — an id of the demand-side namespace (ADR-0014).

Minted only when an evidence rule needs a datum that has no id yet, with a mandatory
definition written at that moment. Uniqueness is guarded by design review plus a lint
(same id, different definition = error); the "dictionary" is a generated view, never a
curated artifact.
"""

from dataclasses import dataclass
from typing import Any


class InvalidDataRequirement(Exception):
    """The data requirement violates a domain invariant."""


@dataclass(frozen=True)
class DataRequirement:
    id: str
    definition: str
    aliases: tuple[str, ...] = ()
    value_domain: dict[str, Any] | None = None
    grounded_in: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidDataRequirement("id is required")
        if not self.definition.strip():
            raise InvalidDataRequirement(
                f"data requirement {self.id}: a definition is mandatory (ADR-0014 — "
                "the definition is written when the id is minted)"
            )
