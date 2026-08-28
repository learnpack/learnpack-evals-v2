"""`Dataset` — a named set of evaluands, and its frozen versions (ADR-0058). Pure Python.

Two levels, because they answer two different questions. The **dataset** is what people talk
about ("the reference set"); its name is a label and binds nothing, so renaming it is not a
change to anything a round measured. A **version** is the membership, frozen: it is what a
campaign is opened against, and it is never edited — editing means minting the next one.

Three rules live here and nowhere else:

- **Only membership bumps.** `rename` mints nothing (ADR-0055's rule: the id identifies, the
  name describes).
- **The note is required.** A version whose reason nobody wrote down makes every earlier
  number invalid *and* uninterpretable, which is strictly worse than one that never changed.
- **A membership equal to the current one is a no-op, not a version.** Detected by hash, and
  refused — the rule `content_hash` (ADR-0027) and `ConsumableUrlDeclared` (ADR-0054) already
  apply: a change is recorded and a no-op is not.

Members are content ids and nothing else. They point at contents that are immutable and never
retired (ADR-0033), which is why a version needs no per-member history: the industry's
per-item revision tables exist because their items carry the expected output, and ours do not
(ADR-0015).
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class InvalidDataset(Exception):
    """The dataset or the version breaks an invariant (blank name, blank note)."""


class DatasetNotFound(Exception):
    """No dataset with that id."""


class EmptyMembership(Exception):
    """A version with no members would freeze a set with nothing in it."""


class UnchangedMembership(Exception):
    """The membership equals the current version's: a no-op is not a version."""


def member_set_hash(members: Iterable[UUID]) -> str:
    """Identity by contents, over the canonical (sorted, de-duplicated) membership.

    Two jobs, both already paid for elsewhere in this codebase. It is what makes the no-op
    detectable without trusting whoever is editing to notice; and it is a key that outlives a
    local database, the way `brief_hash` is published *because the id is not portable*
    (ADR-0039 §4). Order and repetition are not part of what a set is, so neither reaches the
    digest.
    """
    canonical = "\n".join(sorted({str(member) for member in members}))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_members(members: Iterable[UUID]) -> tuple[UUID, ...]:
    """De-duplicated and ordered, so what is stored and what is hashed are the same set."""
    return tuple(sorted(set(members), key=str))


@dataclass(frozen=True)
class DatasetVersion:
    """A frozen membership, with the reason it exists.

    Frozen in the dataclass sense *and* in the domain sense: nothing mutates a version, which
    is why the aggregate has no method that takes one and returns it changed.
    """

    id: UUID
    ordinal: int
    note: str
    members: tuple[UUID, ...]
    member_set_hash: str
    created_by: UUID
    created_at: datetime | None = None


@dataclass
class Dataset:
    """The concept: a name, a description, and the versions that hang from it."""

    id: UUID
    name: str
    created_by: UUID
    description: str | None = None
    versions: tuple[DatasetVersion, ...] = ()
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidDataset("name is required")

    @property
    def latest_version(self) -> DatasetVersion | None:
        """The version a campaign gets when nobody names one. `None` only mid-construction:
        `declare` mints v1 in the same act, because a dataset with no version is not a set."""
        return self.versions[-1] if self.versions else None

    def rename(self, name: str, description: str | None) -> bool:
        """Replace the label whole. This is not a change to the set, so it mints no version.

        Returns whether anything actually changed, so the caller can keep a no-op out of the
        outbox — the same shape `declare_consumable_url` uses, and the same reason: a rename
        that renamed nothing is noise a later reader has to rule out.

        Validates through `__post_init__` so a blank name is refused here by the rule that
        refuses it on the way in — the aggregate owns it and there is no second copy (ADR-0055).
        """
        if name == self.name and description == self.description:
            return False
        self.name = name
        self.description = description
        self.__post_init__()
        return True

    def mint_version(
        self,
        version_id: UUID,
        members: Iterable[UUID],
        note: str,
        created_by: UUID,
        at: datetime | None = None,
    ) -> DatasetVersion:
        """Freeze a membership as the next version, or refuse.

        The three refusals are the decision: an empty set, a missing reason, and a membership
        that changes nothing. The last one is the interesting one — without it the version
        line fills with entries that record an act and no fact, and `v7` stops meaning
        anything more than "somebody pressed save seven times".
        """
        if not note.strip():
            raise InvalidDataset(
                "a version's note is required: it is what makes the numbers of earlier "
                "rounds interpretable once the set has moved"
            )
        frozen = canonical_members(members)
        if not frozen:
            raise EmptyMembership("a version needs at least one course")

        digest = member_set_hash(frozen)
        current = self.latest_version
        if current is not None and current.member_set_hash == digest:
            raise UnchangedMembership(
                f"this membership is already version {current.ordinal}: "
                "a change is recorded and a no-op is not"
            )

        version = DatasetVersion(
            id=version_id,
            ordinal=len(self.versions) + 1,
            note=note,
            members=frozen,
            member_set_hash=digest,
            created_by=created_by,
            created_at=at,
        )
        self.versions = (*self.versions, version)
        return version

    def version(self, version_id: UUID) -> DatasetVersion | None:
        return next((v for v in self.versions if v.id == version_id), None)
