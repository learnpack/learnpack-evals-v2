"""How much a claim follows expert judgment — pure functions, zero imports from other modules.

ADR-0063. A campaign leaves human labels per `(course, quality)`; an assessor version leaves a
status per `(course, claim)`; a claim asserts about exactly one quality (ADR-0026) and the
reference instrument's item IS that quality (ADR-0052 §1). So the two sides meet, and what this
module computes is how well they agree — a property of the pair `(assessor version, claim)`,
which is why it says something about courses the campaign never touched.

Everything here works structurally on already-scoped data, the way `aggregation.py` and
`campaign_report.py` do, so it is unit-testable with trivial fakes.

Two things are deliberately not here. Nothing averages two campaigns (ADR-0063 §7), because
there is no function to call: a caller reads one campaign at a time. And nothing corrects a
course (§9): every number below is about a group.
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

# The four ways a course can sit on the human side of the comparison. `grey` and `absent` are
# both "not in the 2x2" and are counted apart, because one is the panel declining to commit
# and the other is nobody having answered.
HumanVerdict = Literal["accept", "reject", "grey", "absent"]

ACCEPT: HumanVerdict = "accept"
REJECT: HumanVerdict = "reject"
GREY: HumanVerdict = "grey"
ABSENT: HumanVerdict = "absent"

# What the automated side says about a claim (`insufficient` is neither, and stays out).
SUPPORTED = "supported"
REFUTED = "refuted"


@dataclass(frozen=True)
class Thresholds:
    """The bars `classify` applies. Values, not literals buried in the logic.

    ADR-0063 §5: these are reasonable, not measured — the first campaign is what settles them,
    and moving them then should be editing a number rather than rewriting a rule.
    """

    accept_at: int = 4
    reject_at: int = 2
    # Below this many courses in the 2x2 nothing is claimed at all.
    min_sample: int = 10
    # And below this, a verdict is offered but never `tracks`.
    min_sample_to_track: int = 15
    min_kappa: float = 0.6
    # How far under the panel's own agreement the judge may fall (the ETS relative rule).
    max_degradation: float = 0.10
    # A ceiling at or under this leaves nothing to validate against.
    min_ceiling: float = 0.5


DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class Ratio:
    """A proportion that carries its denominator, because `9 of 11` and `82 %` are not the
    same assertion (ADR-0063 §3). `value` is `None` when nothing was measured — never 0."""

    hit: int
    of: int

    @property
    def value(self) -> float | None:
        return self.hit / self.of if self.of else None


@dataclass(frozen=True)
class Confusion:
    """The 2x2 of one claim: rows are what the experts said, columns what the assessor said."""

    supported_accepted: int = 0  # experts accept, assessor says supported — a hit
    refuted_accepted: int = 0  # experts accept, assessor says refuted — missed
    supported_rejected: int = 0  # experts reject, assessor says supported — false alarm
    refuted_rejected: int = 0  # experts reject, assessor says refuted — a hit

    @property
    def accepted(self) -> int:
        return self.supported_accepted + self.refuted_accepted

    @property
    def rejected(self) -> int:
        return self.supported_rejected + self.refuted_rejected

    @property
    def total(self) -> int:
        return self.accepted + self.rejected

    @property
    def has_empty_row(self) -> bool:
        """Either the experts never rejected, or never accepted.

        Then one of the two proportions has no denominator and no number of raters fixes it:
        a claim that never distinguishes anything cannot be shown to distinguish well.
        """
        return self.accepted == 0 or self.rejected == 0


def human_verdict(
    scores: Sequence[int], thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> HumanVerdict:
    """Where one course sits, from the raters who scored its item (ADR-0063 §2).

    The mean of the raters present. Abstentions and derived rows never reach here — nobody
    judged them — so an empty sequence means the item was not answered for this course.
    """
    if not scores:
        return ABSENT
    mean = statistics.fmean(scores)
    if mean >= thresholds.accept_at:
        return ACCEPT
    if mean <= thresholds.reject_at:
        return REJECT
    return GREY


def rater_verdicts(
    scores: Sequence[int], thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> list[HumanVerdict]:
    """The same cut applied to each rater on their own — what the ceiling is measured on.

    The ceiling has to be the same statistic as the judge's agreement or the relative rule
    subtracts two different units (ADR-0063 §4), so the panel is compared with itself on the
    binarisation, not on the raw scale.
    """
    return [human_verdict([score], thresholds) for score in scores]


def confuse(pairs: Sequence[tuple[HumanVerdict, str]]) -> Confusion:
    """The 2x2 over `(human verdict, claim status)` pairs.

    Anything that is not a clean accept/reject on one side and supported/refuted on the other
    is left out: the grey zone, the unanswered items, and the assessor's `insufficient`.
    """
    cells = {"aa": 0, "ar": 0, "ra": 0, "rr": 0}
    for verdict, status in pairs:
        if verdict == ACCEPT and status == SUPPORTED:
            cells["aa"] += 1
        elif verdict == ACCEPT and status == REFUTED:
            cells["ar"] += 1
        elif verdict == REJECT and status == SUPPORTED:
            cells["ra"] += 1
        elif verdict == REJECT and status == REFUTED:
            cells["rr"] += 1
    return Confusion(
        supported_accepted=cells["aa"],
        refuted_accepted=cells["ar"],
        supported_rejected=cells["ra"],
        refuted_rejected=cells["rr"],
    )


def sensitivity(c: Confusion) -> Ratio:
    """Of the courses the experts accepted, on how many did the assessor say `supported`."""
    return Ratio(hit=c.supported_accepted, of=c.accepted)


def specificity(c: Confusion) -> Ratio:
    """Of the courses the experts rejected, on how many did the assessor say `refuted`."""
    return Ratio(hit=c.refuted_rejected, of=c.rejected)


def agreement(c: Confusion) -> float | None:
    """The share the two sides simply agreed on — the judge's half of the relative rule."""
    if not c.total:
        return None
    return (c.supported_accepted + c.refuted_rejected) / c.total


def youden_j(c: Confusion) -> float | None:
    """`sensitivity + specificity - 1`. Grades the claim, and is what a population correction
    would divide by (ADR-0063 §3). At or below zero the claim does not beat chance."""
    sens, spec = sensitivity(c).value, specificity(c).value
    if sens is None or spec is None:
        return None
    return sens + spec - 1


def cohen_kappa(c: Confusion) -> float | None:
    """Agreement corrected for what chance alone would produce.

    `None` — never 0 — when there is nothing to correct: an empty table, or one where both
    sides always said the same thing, which makes the expected agreement 1 and the coefficient
    undefined rather than perfect.
    """
    n = c.total
    if not n:
        return None
    observed = (c.supported_accepted + c.refuted_rejected) / n
    said_supported = c.supported_accepted + c.supported_rejected
    said_refuted = c.refuted_accepted + c.refuted_rejected
    expected = (c.accepted * said_supported + c.rejected * said_refuted) / (n * n)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def pairwise_agreement(per_content_verdicts: Sequence[Sequence[HumanVerdict]]) -> float | None:
    """The ceiling: how often two raters of the same course landed on the same side.

    Pairs are formed **inside one course**, because that is the only place two answers are
    about the same thing, and then pooled over the campaign — the shape ADR-0060 §5 fixed.
    A course where either rater lands in the grey zone contributes no pair: the cut has to be
    the same one the judge is measured against, and grey is not a side.

    `None` when no course produced a pair. Zero would read as "they never agreed", which is a
    lie about a measurement nobody could take.
    """
    agreed = 0
    pairs = 0
    for verdicts in per_content_verdicts:
        sides = [v for v in verdicts if v in (ACCEPT, REJECT)]
        for i in range(len(sides)):
            for j in range(i + 1, len(sides)):
                pairs += 1
                if sides[i] == sides[j]:
                    agreed += 1
    return agreed / pairs if pairs else None


Status = Literal["tracks", "weak", "unvalidated"]

TRACKS: Status = "tracks"
WEAK: Status = "weak"
UNVALIDATED: Status = "unvalidated"


@dataclass(frozen=True)
class Verdict:
    """What the row says about the claim, and why it says it."""

    status: Status
    reason: str | None = None


def classify(
    c: Confusion,
    ceiling: float | None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> Verdict:
    """`tracks | weak | unvalidated`, by the rule of ADR-0063 §5.

    The order of the `unvalidated` checks is the order of the questions: *is there anything
    to read* before *is there anything to compare against* before *is it good enough*.
    """
    if c.total < thresholds.min_sample:
        return Verdict(UNVALIDATED, "too_few")
    if c.has_empty_row:
        # The experts never landed on one side, so one of the two proportions has no
        # denominator. More raters would not help; the claim never varies.
        return Verdict(UNVALIDATED, "no_variance")
    if ceiling is None or ceiling <= thresholds.min_ceiling:
        # The panel does not agree with itself, so there is no human answer to match
        # (ADR-0015 §5). The defect is the form's, and the claim stays unjudged.
        return Verdict(UNVALIDATED, "ceiling_too_low")

    kappa = cohen_kappa(c)
    judge = agreement(c)
    if kappa is None or judge is None:
        return Verdict(UNVALIDATED, "no_variance")

    if c.total < thresholds.min_sample_to_track:
        return Verdict(WEAK, "sample_below_tracking")
    if kappa < thresholds.min_kappa:
        return Verdict(WEAK, "kappa_below_bar")
    if ceiling - judge > thresholds.max_degradation:
        return Verdict(WEAK, "degrades_from_ceiling")
    return Verdict(TRACKS)
