"""EvaluationStudy — the round, named (12-define §Studies, 13-code §3.6).

Root aggregate; it owns the **name** (and an optional description), the **selection**
(instrument version + assessor), the **recipe** (briefIds × generator scope) and the
**materialized dataset** (contentIds). Cycle: declared → prepared → open → signed_off.

Invariants (12-define, amended by ADR-0042, by ADR-0043 §1 and by ADR-0044 §2): while the
study is a draft the four choices REPLACE FREELY, because nothing can consume them yet — a
batch refuses any study that is not open. **`open()` is the pin**: from it the triple is
immutable, which is the whole property ADR-0042 bought and the only form in which the rule
ever did any work · the dataset and the scope that selected it are fixed at the same
moment · signed off means an
immutable report, never re-emitted — signing off is a human act, and what it adds is the
signature, not the visibility (ADR-0041, ADR-0043 §8).
`prepared` is derived: declared + every choice + composed, in any order, and it is not a
state a reader is shown.

The name is not the study's *purpose*: the GLOSSARY reserves that word for a typology
(initial / regression / comparison) nobody has needed to build (ADR-0043 §7) — and the
recipe's **generator scope** is why it stays unbuilt, since a scope naming one version is a
measurement and one naming several is a comparison (ADR-0044 §9).

The judge is the third leg of what makes a result reproducible: the triple dataset ×
instrument version × assessor. `assessor_id` is nullable both because a draft may not have
chosen one yet and because studies that predate ADR-0042 exist and are read as they were —
the invariant binds what happens at `open`, not the reconstruction of a row written before
the decision.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final
from uuid import UUID


class _AllGenerators:
    """Every generator version the briefs bring — **said**, not left unsaid.

    It is a value and not an empty list because the two readings of "no versions named"
    are the whole defect ADR-0044 closes: one means "all of them" and the other means
    "nobody has decided yet", and a recipe cannot afford to have them look alike."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "ALL_GENERATORS"


ALL_GENERATORS: Final = _AllGenerators()

#: What a study measures: every version the briefs bring, or exactly these (never empty).
GeneratorScope = _AllGenerators | tuple[UUID, ...]


class InvalidStudy(Exception):
    """The study violates a domain invariant (blank name)."""


class StudyNotFound(Exception):
    """No study with that id."""


class InstrumentNotChosen(Exception):
    """Opening pins the norm, so there has to be one to pin."""


class AssessorNotChosen(Exception):
    """Opening pins the judge too — a study's result is a triple."""


class GeneratorScopeNotDeclared(Exception):
    """Opening fixes what the round measures, so it has to have been said (ADR-0044 §2)."""


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
    # The recipe's second axis (ADR-0044). `None` is "not declared yet" and lives only in a
    # draft: `open()` refuses it, the way it refuses a study with no instrument.
    generator_scope: GeneratorScope | None = None
    content_ids: tuple[UUID, ...] = ()
    created_at: datetime | None = None
    opened_at: datetime | None = None
    signed_off_at: datetime | None = None
    signed_off_by: UUID | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidStudy("name is required")

    def select_instrument(self, instrument_version_id: str) -> None:
        """Choose the norm, replaceably, while the study is still a draft.

        No event of its own, exactly like the dataset: nothing has read this yet, and the
        act worth recording is the one that makes it binding (ADR-0043 §2)."""
        self._require_mutable()
        self.instrument_version_id = instrument_version_id
        self._maybe_prepare()

    def select_assessor(self, assessor_id: UUID | None) -> None:
        """Choose the judge, replaceably. `None` clears it — which is what re-pointing a
        draft at a norm this judge never ratified leaves behind.

        Whether it MAY judge the chosen version is the application's question
        (ratification, ADR-0019); the aggregate holds only the draft-or-not rule."""
        self._require_mutable()
        self.assessor_id = assessor_id
        self._maybe_prepare()

    def compose_dataset(
        self,
        brief_ids: tuple[UUID, ...],
        generator_scope: GeneratorScope | None,
        content_ids: tuple[UUID, ...],
    ) -> None:
        """Replace recipe + dataset while the study is still composable. No event of its
        own (13-code §5): the recipe evolves freely until open fixes it.

        The recipe has two axes and they move together, because the dataset is what they
        select between them: a scope changed without re-materializing would describe a
        population the contents do not belong to.

        `None` is a draft that has not declared its scope yet — which is a legitimate half
        of a draft and an impossible study: `open()` is where the declaration is demanded
        (ADR-0044 §2), and a dataset composed before it is provisional like everything else
        a draft holds."""
        self._require_mutable()
        if isinstance(generator_scope, tuple) and not generator_scope:
            # The one value that could be read as either form, refused where the rule lives.
            raise InvalidStudy(
                "a listed generator scope cannot be empty: it would select nothing. "
                "Declare every version instead if that is what the round measures"
            )
        self.brief_ids = tuple(brief_ids)
        self.generator_scope = generator_scope
        self.content_ids = tuple(content_ids)
        self._maybe_prepare()

    def open(self, at: datetime) -> None:
        if self.status == "signed_off":
            raise StudyAlreadySignedOff(f"study {self.id} is signed off")
        if self.status == "open":
            raise StudyAlreadyOpen(f"study {self.id} is already open")
        if self.instrument_version_id is None:
            raise InstrumentNotChosen(f"study {self.id} has no instrument")
        if self.assessor_id is None:
            raise AssessorNotChosen(f"study {self.id} has no judge")
        if self.generator_scope is None:
            raise GeneratorScopeNotDeclared(
                f"study {self.id} has not declared which generator versions it measures"
            )
        if not self.content_ids:
            raise DatasetEmpty(f"study {self.id} has an empty dataset")
        # THE pin: from here the triple is what this study's result is defined by, and the
        # aggregate refuses every change to it (`_require_mutable`).
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
        """`prepared` means "everything opening needs is here" — so it waits for both
        choices. Internal: the console shows a draft, whichever of the two it is."""
        if (
            self.status == "declared"
            and self.instrument_version_id is not None
            and self.assessor_id is not None
            and self.generator_scope is not None
            and self.content_ids
        ):
            self.status = "prepared"
