"""The examinee's declared identity, in two grains (ADR-0031).

A `Generator` is the lineage — the thing a study means when it says "this generator regressed".
A `GeneratorVersion` is one registered state of it, and the individual of the genetic-algorithm
experiment (ADR-0023): an individual is a configuration that can be *run*, and a lineage cannot.

The lineage exists as a row because it used to exist only as a string retyped at every version
registration, where a typo silently minted a second lineage that no unique constraint could
catch. Now the name is typed once per generator, and a version selects its parent by id.

`GeneratorVersion` is immutable: a genuinely different generator means a new registration, never
an edit. That covers every step of its workflow — there is no sub-component versioning axis
(ADR-0030 §4), and the lineage is not one either: it groups whole versions. The identity is
declarative and unverifiable from inside the system (the generator lives outside); unregistered
drift is a standard diagnosis cause, not something we can detect.

`metadata` carries optional **reference data a version declares about itself** — today
`changelog`, prose for a human reading a report (ADR-0030 §2). It annotates a version; it never
versions anything. Being part of the declared identity, it is write-once. It lives on the version
and not on the lineage on purpose: a blob on the lineage is where the generator internals
ADR-0030 §1 removed from this system would come back.

The generator's *internals* — prompts, workflow steps, configuration — are not held here at all.
Generator-**produced** data is untouched by that: it is evidence, and it arrives as package
artifacts (ADR-0017/0027) and the `GenerationBrief` (ADR-0022).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


class InvalidGenerator(Exception):
    """The generator lineage violates a domain invariant."""


class InvalidGeneratorVersion(Exception):
    """The generator version violates a domain invariant."""


@dataclass(frozen=True)
class Generator:
    """The lineage. It declares its name and nothing else (ADR-0031 §2)."""

    id: UUID
    name: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidGenerator("name is required")


@dataclass(frozen=True)
class GeneratorVersion:
    id: UUID
    generator_id: UUID
    version: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise InvalidGeneratorVersion("version is required")


# --- The lineage's naming rules (ADR-0031 §4, §5) -----------------------------------------
#
# Two forms, for two different jobs. `normalized_name` is the identity key and is enforced by a
# unique index over the same expression; `canonical_name` is looser and is read only by the
# near-miss guard, which refuses but can be overridden. A constraint may never use the looser
# one: folding `gen_a` into `gen-a` is a good hint and a bad law.

_SEPARATORS = "_. "


def normalized_name(raw: str) -> str:
    """The lineage key: case and whitespace folded, which are the two variations a keyboard
    produces without meaning to. `lower(btrim(name))` in the store, plus collapsed inner runs —
    a name is a label, and two spaces inside one never meant a second lineage."""
    return " ".join(raw.split()).lower()


def canonical_name(raw: str) -> str:
    """`normalized_name` with separators folded too, so `learnpack_gen`, `learnpack.gen` and
    `learnpack gen` compare equal. Guard-only: two teams could legitimately spell their
    conventions differently, so this decides what to *ask about*, never what to refuse."""
    normalized = normalized_name(raw)
    for separator in _SEPARATORS:
        normalized = normalized.replace(separator, "-")
    return normalized


def edit_distance(a: str, b: str, *, cap: int) -> int:
    """Levenshtein distance, abandoned once it is known to exceed `cap`.

    Returns `cap + 1` for anything further apart: the guard only ever asks "is this close?", so
    computing how far away an unrelated name is would be work nobody reads.
    """
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    if a == b:
        return 0

    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, start=1):
        current = [i]
        for j, right in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + (left != right),  # substitution
                )
            )
        if min(current) > cap:
            return cap + 1
        previous = current
    return min(previous[-1], cap + 1)


NEAR_MISS_DISTANCE = 2
"""Flat, not scaled by length: the typo classes this catches — transposition, a doubled letter,
a dropped letter, the wrong separator, the wrong case — are all within two edits whatever the
name's length, and a scaled rule cannot be explained inside the refusal message (ADR-0031)."""

SHORT_NAME_LENGTH = 4
"""At or below this length almost every name is two edits from every other, so the threshold
drops to one. Without it the guard would refuse most short names against each other."""


def nearest_name(
    candidate: str, existing: Iterable[str], *, max_distance: int = NEAR_MISS_DISTANCE
) -> str | None:
    """The registered name `candidate` is close enough to be a typo of, or None.

    Compares canonical forms and returns the existing name **as it was declared**, so whoever
    reads the refusal recognizes what it names. Ties go to the first match in `existing`, which
    the repository orders by registration — the older lineage is the likelier thing to be
    fat-fingering.
    """
    key = canonical_name(candidate)
    cap = 1 if len(key) <= SHORT_NAME_LENGTH else max_distance
    for name in existing:
        if edit_distance(key, canonical_name(name), cap=cap) <= cap:
            return name
    return None


def resolve_declared_generator_version(
    declared_name: str,
    declared_version: str,
    generators: Iterable[Generator],
    versions: Iterable[GeneratorVersion],
) -> GeneratorVersion | None:
    """The registered `GeneratorVersion` a package's self-declared generator names, or None.

    The lineage is matched by `normalized_name` — the same identity key its unique index
    enforces, not the looser `canonical_name` the near-miss guard uses: this is a lookup, not a
    typo guard, and folding separators here would silently match a lineage the package did not
    actually name. The version is matched by exact string, because versions are declarative
    (ADR-0005) and `UNIQUE(generatorId, version)` never fuzzy-matches one either.
    """
    key = normalized_name(declared_name)
    generator = next((g for g in generators if normalized_name(g.name) == key), None)
    if generator is None:
        return None
    return next(
        (v for v in versions if v.generator_id == generator.id and v.version == declared_version),
        None,
    )
