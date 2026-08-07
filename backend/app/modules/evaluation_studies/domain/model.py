"""EvaluationStudy — the round with a purpose (12-define §Studies, 13-code §3.6).

Root aggregate; it owns the purpose, the pin, the **recipe** (briefIds) and the
**materialized dataset** (contentIds). Cycle: declared → prepared → open → published.
Invariants (12-define): the instrument is pinned ONCE, before opening, immutable
afterwards · the dataset is fixed at open · published means an immutable report, never
re-emitted — publishing is a human act. `prepared` is derived: declared + pinned +
composed, in either order.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


class InvalidStudy(Exception):
    """The study violates a domain invariant (blank purpose)."""


class StudyNotFound(Exception):
    """No study with that id."""


class InstrumentAlreadyPinned(Exception):
    """The pin happens once; afterwards the instrument version is immutable."""


class InstrumentNotPinned(Exception):
    """Opening requires the pinned norm to exist first."""


class DatasetLocked(Exception):
    """The dataset is fixed at open; composing afterwards is impossible."""


class DatasetEmpty(Exception):
    """Opening an empty study would fix a dataset with nothing to judge."""


class StudyAlreadyOpen(Exception):
    """The study is already open."""


class StudyNotOpen(Exception):
    """Publishing reports on an open round; this study never opened."""


class StudyAlreadyPublished(Exception):
    """Published means immutable, never re-emitted."""


@dataclass
class Study:
    id: UUID
    purpose: str
    status: str = "declared"
    instrument_version_id: str | None = None
    brief_ids: tuple[UUID, ...] = ()
    content_ids: tuple[UUID, ...] = ()
    created_at: datetime | None = None
    opened_at: datetime | None = None
    published_at: datetime | None = None
    published_by: UUID | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise InvalidStudy("purpose is required")

    def pin_instrument(self, instrument_version_id: str) -> None:
        # Pinned-once first: an open/published study is necessarily pinned, and THAT is
        # the answer the caller needs, not the lifecycle state.
        if self.instrument_version_id is not None:
            raise InstrumentAlreadyPinned(
                f"study {self.id} already pins {self.instrument_version_id}"
            )
        self._require_mutable()
        self.instrument_version_id = instrument_version_id
        self._maybe_prepare()

    def compose_dataset(self, brief_ids: tuple[UUID, ...], content_ids: tuple[UUID, ...]) -> None:
        """Replace recipe + dataset while the study is still composable. No event of its
        own (13-code §5): the recipe evolves freely until open fixes it."""
        self._require_mutable()
        self.brief_ids = tuple(brief_ids)
        self.content_ids = tuple(content_ids)
        self._maybe_prepare()

    def open(self, at: datetime) -> None:
        if self.status == "published":
            raise StudyAlreadyPublished(f"study {self.id} is published")
        if self.status == "open":
            raise StudyAlreadyOpen(f"study {self.id} is already open")
        if self.instrument_version_id is None:
            raise InstrumentNotPinned(f"study {self.id} has no pinned instrument")
        if not self.content_ids:
            raise DatasetEmpty(f"study {self.id} has an empty dataset")
        self.status = "open"
        self.opened_at = at

    def publish(self, by: UUID, at: datetime) -> None:
        if self.status == "published":
            raise StudyAlreadyPublished(f"study {self.id} is published")
        if self.status != "open":
            raise StudyNotOpen(f"study {self.id} is {self.status}, not open")
        self.status = "published"
        self.published_by = by
        self.published_at = at

    def _require_mutable(self) -> None:
        if self.status == "published":
            raise StudyAlreadyPublished(f"study {self.id} is published")
        if self.status == "open":
            raise DatasetLocked(f"study {self.id} is open; its composition is fixed")

    def _maybe_prepare(self) -> None:
        if (
            self.status == "declared"
            and self.instrument_version_id is not None
            and self.content_ids
        ):
            self.status = "prepared"
