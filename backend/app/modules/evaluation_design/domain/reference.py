"""DataRequirement — an id of the demand-side namespace (ADR-0014).

Minted only when an evidence rule needs a datum that has no id yet, with a mandatory
definition AND a mandatory value domain written at that moment. Uniqueness is guarded by
design review plus a lint (same id, different definition = error); the "dictionary" is a
generated view, never a curated artifact.

The definition says what the datum means; the `value_domain` says what shape it takes
(ADR-0020). Both are mandatory because both are the contract an extraction adapter
declares its capabilities against — a shape left in prose is a shape nothing can check.
"""

from dataclasses import dataclass
from typing import Any

from app.shared.domain.value_domain import validate_spec


class InvalidDataRequirement(Exception):
    """The data requirement violates a domain invariant."""


@dataclass(frozen=True)
class DataRequirement:
    id: str
    definition: str
    value_domain: dict[str, Any]
    aliases: tuple[str, ...] = ()
    grounded_in: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidDataRequirement("id is required")
        if not self.definition.strip():
            raise InvalidDataRequirement(
                f"data requirement {self.id}: a definition is mandatory (ADR-0014 — "
                "the definition is written when the id is minted)"
            )
        if not self.value_domain:
            raise InvalidDataRequirement(
                f"data requirement {self.id}: a value_domain is mandatory (ADR-0020 — "
                "the shape is declared where the id is minted, so extraction can be "
                "checked against it)"
            )
        problems = validate_spec(self.value_domain, f"data requirement {self.id}: value_domain")
        if problems:
            raise InvalidDataRequirement("; ".join(problems))
