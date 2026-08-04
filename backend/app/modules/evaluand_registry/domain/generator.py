"""GeneratorVersion — the declared identity of the examinee (GLOSSARY, design 12 §Registry).

Immutable by design: a genuinely different generator means a new registration, never an
edit. The identity is declarative and unverifiable from inside the system (the generator
lives outside); unregistered drift is a standard diagnosis cause, not something we can
detect. Config fields stay inside the free-form metadata blob until something consumes
them (demand-driven promotion).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


class InvalidGeneratorVersion(Exception):
    """The generator version violates a domain invariant."""


class InvalidGeneratorArtifact(Exception):
    """The generator artifact violates a domain invariant."""


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


@dataclass(frozen=True)
class GeneratorArtifact:
    """A generator-level artifact, shared across its contents.

    Registered now, profiled only when a claim needs it (first-increment mark in
    design 13). `kind` is an open vocabulary — no enum in the domain.
    """

    id: UUID
    generator_version_id: UUID
    kind: str
    locator: str
    format: str | None = None

    def __post_init__(self) -> None:
        for attr in ("kind", "locator"):
            if not getattr(self, attr).strip():
                raise InvalidGeneratorArtifact(f"{attr} is required")
