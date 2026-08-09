"""GeneratorVersion — the declared identity of the examinee (GLOSSARY, design 12 §Registry).

Immutable by design: a genuinely different generator means a new registration, never an
edit. That covers every step of its workflow — there is no sub-component versioning axis
(ADR-0030 §4). The identity is declarative and unverifiable from inside the system (the
generator lives outside); unregistered drift is a standard diagnosis cause, not something
we can detect.

`metadata` carries optional **reference data a version declares about itself** — today
`changelog`, prose for a human reading a report (ADR-0030 §2). It annotates a version; it
never versions anything. Being part of the declared identity, it is write-once. Keys stay
in the blob until something consumes them (demand-driven promotion).

The generator's *internals* — prompts, workflow steps, configuration — are not held here at
all (ADR-0030 §1). Generator-**produced** data is untouched by that: it is evidence, and it
arrives as package artifacts (ADR-0017/0027) and the `GenerationBrief` (ADR-0022).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


class InvalidGeneratorVersion(Exception):
    """The generator version violates a domain invariant."""


@dataclass(frozen=True)
class GeneratorVersion:
    id: UUID
    name: str
    version: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for attr in ("name", "version"):
            if not getattr(self, attr).strip():
                raise InvalidGeneratorVersion(f"{attr} is required")
