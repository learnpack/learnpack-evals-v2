"""ContentPackage — the complete work product a generator delivers (GLOSSARY).

The registry captures the package, not just a consumable URL: internal artifacts
(manifests, knowledge graphs, item banks) are usually the best evidence for extraction
(ADR-0009). `kind` is an open vocabulary — no enum in the domain; a new kind is data,
not code. Mirrors the validated/trusted split of `metadata.py`.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


class InvalidPackage(Exception):
    """The content package violates a domain invariant."""


@dataclass(frozen=True)
class PackageArtifact:
    kind: str
    locator: str
    format: str | None = None

    def __post_init__(self) -> None:
        for attr in ("kind", "locator"):
            if not getattr(self, attr).strip():
                raise InvalidPackage(f"artifact {attr} is required")


@dataclass(frozen=True)
class ContentPackage:
    artifacts: tuple[PackageArtifact, ...] = ()

    @classmethod
    def validated(cls, artifacts: Iterable[Mapping[str, str | None]]) -> "ContentPackage":
        """Build from raw input, enforcing invariants (registration path)."""
        return cls(
            artifacts=tuple(
                PackageArtifact(
                    kind=str(raw.get("kind") or ""),
                    locator=str(raw.get("locator") or ""),
                    format=raw.get("format") or None,
                )
                for raw in artifacts
            )
        )

    @classmethod
    def trusted(cls, artifacts: Iterable[PackageArtifact]) -> "ContentPackage":
        """Rehydrate what is already persisted, without revalidating."""
        return cls(artifacts=tuple(artifacts))
