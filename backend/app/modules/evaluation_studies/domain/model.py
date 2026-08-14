"""EvaluationStudy — the round, named (12-define §Studies, 13-code §3.6).

Root aggregate; it owns the **name** (and an optional description), the **two pins**, the
**recipe** (briefIds) and the **materialized dataset** (contentIds).
Cycle: declared → prepared → open → signed_off.
Invariants (12-define, amended by ADR-0042): the instrument **and the assessor** are each
pinned ONCE, before opening, immutable afterwards · the dataset is fixed at open ·
signed off means an immutable report, never re-emitted — signing off is a human act, and
what it adds is the signature, not the visibility (ADR-0041, ADR-0043 §8).
`prepared` is derived: declared + both pins + composed, in any order.

The name is not the study's *purpose*: the GLOSSARY reserves that word for a typology
(initial / regression / comparison) nobody has needed to build (ADR-0043 §7).

The second pin is what makes a study's result reproducible: it is the triple dataset ×
instrument version × assessor, and only two thirds of it used to be fixed. `assessor_id`
is nullable because studies that predate the decision exist and are read as they were —
the invariant binds the ACTS, not the reconstruction of a row written before it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


class InvalidStudy(Exception):
    """The study violates a domain invariant (blank name)."""


class StudyNotFound(Exception):
    """No study with that id."""


class InstrumentAlreadyPinned(Exception):
    """The pin happens once; afterwards the instrument version is immutable."""


class InstrumentNotPinned(Exception):
    """Opening requires the pinned norm to exist first."""


class AssessorAlreadyPinned(Exception):
    """The pin happens once; afterwards the assessor is immutable (ADR-0042 §8)."""


class AssessorNotPinned(Exception):
    """Opening requires the judge to be named — a study's result is a triple."""


class DatasetLocked(Exception):
    """The dataset is fixed at open; composing afterwards is impossible."""


class DatasetEmpty(Exception):
    """Opening an empty study would fix a dataset with nothing to judge."""


class StudyAlreadyOpen(Exception):
    """The study is already open."""


class StudyNotOpen(Exception):
    """Signing off reports on an open round; this study never opened."""


class StudyAlreadySignedOff(Exception):
    """Signed off means immutable, never re-emitted."""


@dataclass
class Study:
    id: UUID
    name: str
    status: str = "declared"
    # Optional, and never defaulted from the name: an absent description is absent.
    description: str | None = None
    instrument_version_id: str | None = None
    # Null on studies declared before ADR-0042; every read then behaves as it did.
    assessor_id: UUID | None = None
    brief_ids: tuple[UUID, ...] = ()
    content_ids: tuple[UUID, ...] = ()
    created_at: datetime | None = None
    opened_at: datetime | None = None
    signed_off_at: datetime | None = None
    signed_off_by: UUID | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidStudy("name is required")

    def pin_instrument(self, instrument_version_id: str) -> None:
        # Pinned-once first: an open or signed-off study is necessarily pinned, and THAT is
        # the answer the caller needs, not the lifecycle state.
        if self.instrument_version_id is not None:
            raise InstrumentAlreadyPinned(
                f"study {self.id} already pins {self.instrument_version_id}"
            )
        self._require_mutable()
        self.instrument_version_id = instrument_version_id
        self._maybe_prepare()

    def pin_assessor(self, assessor_id: UUID) -> None:
        """Name the judge, once. Whether it may judge this instrument version is the
        application's question (ratification, ADR-0019); the aggregate only holds the
        once-and-before-open rule, which is the instrument pin's rule exactly."""
        if self.assessor_id is not None:
            raise AssessorAlreadyPinned(f"study {self.id} already pins {self.assessor_id}")
        self._require_mutable()
        self.assessor_id = assessor_id
        self._maybe_prepare()

    def compose_dataset(self, brief_ids: tuple[UUID, ...], content_ids: tuple[UUID, ...]) -> None:
        """Replace recipe + dataset while the study is still composable. No event of its
        own (13-code §5): the recipe evolves freely until open fixes it."""
        self._require_mutable()
        self.brief_ids = tuple(brief_ids)
        self.content_ids = tuple(content_ids)
        self._maybe_prepare()

    def open(self, at: datetime) -> None:
        if self.status == "signed_off":
            raise StudyAlreadySignedOff(f"study {self.id} is signed off")
        if self.status == "open":
            raise StudyAlreadyOpen(f"study {self.id} is already open")
        if self.instrument_version_id is None:
            raise InstrumentNotPinned(f"study {self.id} has no pinned instrument")
        if self.assessor_id is None:
            raise AssessorNotPinned(f"study {self.id} has no pinned assessor")
        if not self.content_ids:
            raise DatasetEmpty(f"study {self.id} has an empty dataset")
        self.status = "open"
        self.opened_at = at

    def sign_off(self, by: UUID, at: datetime) -> None:
        if self.status == "signed_off":
            raise StudyAlreadySignedOff(f"study {self.id} is signed off")
        if self.status != "open":
            raise StudyNotOpen(f"study {self.id} is {self.status}, not open")
        self.status = "signed_off"
        self.signed_off_by = by
        self.signed_off_at = at

    def _require_mutable(self) -> None:
        if self.status == "signed_off":
            raise StudyAlreadySignedOff(f"study {self.id} is signed off")
        if self.status == "open":
            raise DatasetLocked(f"study {self.id} is open; its composition is fixed")

    def _maybe_prepare(self) -> None:
        """`prepared` means "everything opening needs is here" — so it waits for both pins."""
        if (
            self.status == "declared"
            and self.instrument_version_id is not None
            and self.assessor_id is not None
            and self.content_ids
        ):
            self.status = "prepared"
