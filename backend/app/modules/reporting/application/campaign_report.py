"""Campaign-grain aggregation — pure functions, zero imports from other modules.

ADR-0060 moves the primary axis of the human report from `content × item` to
`item × campaign`. The arithmetic reason is here: with two assessors per course, a
content-level cell holds exactly one pair of answers, and forty of those pairs are what says
whether an item is answerable at all (ADR-0052 §5).

Everything in this module is fed already-scoped data — the evaluations that belong to one
campaign, by the rule of ADR-0060 §1 — so nothing here knows what a campaign is. Scoping is
the read model's job (`infrastructure/campaign_report.py`); measuring is this one's.

Sits beside `aggregation.py` and reuses it rather than restating it: repetitions still
collapse to the latest per assessor (ADR-0005/0006), an abstention is still not a zero, and a
derived row is still nobody's judgement (ADR-0053).
"""

import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ItemAgreement:
    """How the panel agreed on one item, pooled over the courses of a campaign (ADR-0060 §5).

    Pairs are formed **inside one course**, because that is the only place two answers are
    about the same thing, and then pooled. All fields are `None` when no course produced a
    pair: `Dispersion`'s rule, for its reason — `0` would read as perfect agreement, which is
    a lie about a measurement nobody could take.
    """

    pair_count: int
    content_count: int
    mean_abs_diff: float | None
    exact_pct: float | None
    # Adjacent answers on a Likert scale are not the disagreement `exact_pct` reports them to
    # be (ADR-0060 §5): "agree" beside "strongly agree" is two people saying the same thing
    # with different emphasis.
    within_one_pct: float | None


@dataclass(frozen=True)
class ContentItemAnswers:
    """One item's answers for one course, from the assessors this campaign counted.

    The three fields are the three states a cell can be in (ADR-0060 §4), and they are kept
    apart all the way to the screen: `scores` is what somebody judged, `abstentions` is what
    somebody was asked and could not judge (ADR-0052 §4), and `withheld` is that nobody was
    asked at all because the course declares nothing the item is about (ADR-0053).
    """

    scores: tuple[int, ...]
    abstentions: int = 0
    withheld: bool = False


@dataclass(frozen=True)
class ItemSummary:
    """One item, read across the campaign."""

    distribution: dict[int, int]
    # `None` when nobody scored it — never 0, which reads as the worst answer on the scale.
    average: float | None
    scored_count: int
    abstentions: int
    withheld_contents: int
    # Courses where at least one assessor answered — the denominator every other count on
    # this row is read against (ADR-0011 §3: a number without its own denominator is a
    # coverage claim nobody checked).
    answered_contents: int
    agreement: ItemAgreement


def pooled_agreement(per_content_scores: Sequence[Sequence[int]]) -> ItemAgreement:
    """Pairs within each course, pooled across courses."""
    pairs: list[tuple[int, int]] = []
    contributing = 0
    for scores in per_content_scores:
        count = len(scores)
        if count < 2:
            continue
        contributing += 1
        pairs.extend((scores[i], scores[j]) for i in range(count) for j in range(i + 1, count))

    if not pairs:
        return ItemAgreement(
            pair_count=0,
            content_count=contributing,
            mean_abs_diff=None,
            exact_pct=None,
            within_one_pct=None,
        )

    differences = [abs(a - b) for a, b in pairs]
    return ItemAgreement(
        pair_count=len(pairs),
        content_count=contributing,
        mean_abs_diff=round(statistics.fmean(differences), 3),
        exact_pct=round(100 * sum(1 for d in differences if d == 0) / len(pairs), 1),
        within_one_pct=round(100 * sum(1 for d in differences if d <= 1) / len(pairs), 1),
    )


def response_distribution(scores: Sequence[int], scale_min: int, scale_max: int) -> dict[int, int]:
    """Counts per point of the scale, every point present.

    The whole scale, including the points nobody chose: a distribution missing its empty ends
    cannot be told apart from a shorter scale, and the shape is the reason to show a
    distribution instead of a mean (ADR-0011).
    """
    counts = {point: 0 for point in range(scale_min, scale_max + 1)}
    for score in scores:
        if score in counts:
            counts[score] += 1
    return counts


def summarise_item(
    answers: Sequence[ContentItemAnswers], scale_min: int, scale_max: int
) -> ItemSummary:
    """One item's whole row: what was answered, what was not, and how well it agreed."""
    flat = [score for answer in answers for score in answer.scores]
    return ItemSummary(
        distribution=response_distribution(flat, scale_min, scale_max),
        average=round(statistics.fmean(flat), 2) if flat else None,
        scored_count=len(flat),
        abstentions=sum(answer.abstentions for answer in answers),
        withheld_contents=sum(1 for answer in answers if answer.withheld),
        answered_contents=sum(1 for answer in answers if answer.scores),
        agreement=pooled_agreement([answer.scores for answer in answers]),
    )


@dataclass(frozen=True)
class ContentDisagreement:
    """How far apart the panel was on one course, across its items.

    Two numbers because they rank differently and both are worth reading: the mean says a
    course was read differently throughout, the maximum says one item was contested. A course
    with a single assessor has neither — there is nothing to disagree with.
    """

    mean_abs_diff: float | None
    max_abs_diff: int | None
    contested_items: int


def content_disagreement(per_item_scores: Sequence[Sequence[int]]) -> ContentDisagreement:
    differences: list[int] = []
    contested = 0
    for scores in per_item_scores:
        count = len(scores)
        if count < 2:
            continue
        item_differences = [
            abs(scores[i] - scores[j]) for i in range(count) for j in range(i + 1, count)
        ]
        differences.extend(item_differences)
        if max(item_differences) > 0:
            contested += 1

    if not differences:
        return ContentDisagreement(mean_abs_diff=None, max_abs_diff=None, contested_items=0)
    return ContentDisagreement(
        mean_abs_diff=round(statistics.fmean(differences), 3),
        max_abs_diff=max(differences),
        contested_items=contested,
    )
