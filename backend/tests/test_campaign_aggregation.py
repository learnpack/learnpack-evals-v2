"""Campaign-grain aggregation (ADR-0060) — pure, no DB.

Every expectation is a number computed by hand, so a wrong aggregation cannot pass by
agreeing with itself.
"""

from app.modules.reporting.application import campaign_report
from app.modules.reporting.application.campaign_report import ContentItemAnswers

SCALE = (1, 5)


def answers(*scores: int, abstentions: int = 0, withheld: bool = False) -> ContentItemAnswers:
    return ContentItemAnswers(scores=tuple(scores), abstentions=abstentions, withheld=withheld)


# ------------------------------------------------------------------- pooled agreement


def test_pairs_are_formed_inside_a_course_and_pooled_across_them():
    # Two courses, one pair each: |4-4| = 0 and |2-5| = 3.
    result = campaign_report.pooled_agreement([[4, 4], [2, 5]])

    assert result.pair_count == 2
    assert result.content_count == 2
    assert result.mean_abs_diff == 1.5
    assert result.exact_pct == 50.0
    assert result.within_one_pct == 50.0


def test_answers_are_never_paired_across_courses():
    """Two courses with one assessor each produce no pair at all.

    The two answers are about different courses, so comparing them would measure nothing —
    and reporting `0` would claim a perfect agreement nobody demonstrated.
    """
    result = campaign_report.pooled_agreement([[4], [4]])

    assert result.pair_count == 0
    assert result.content_count == 0
    assert result.mean_abs_diff is None
    assert result.exact_pct is None
    assert result.within_one_pct is None


def test_adjacent_answers_are_a_disagreement_only_for_exact_agreement():
    result = campaign_report.pooled_agreement([[3, 4], [5, 4]])

    assert result.exact_pct == 0.0
    assert result.within_one_pct == 100.0
    assert result.mean_abs_diff == 1.0


def test_three_assessors_on_one_course_make_three_pairs():
    # |2-4| = 2, |2-5| = 3, |4-5| = 1 → mean 2.0, none exact, one within one.
    result = campaign_report.pooled_agreement([[2, 4, 5]])

    assert result.pair_count == 3
    assert result.mean_abs_diff == 2.0
    assert result.exact_pct == 0.0
    assert round(result.within_one_pct or 0, 1) == 33.3


# --------------------------------------------------------------------- distributions


def test_the_distribution_carries_every_point_of_the_scale():
    result = campaign_report.response_distribution([4, 4, 5], *SCALE)

    assert result == {1: 0, 2: 0, 3: 0, 4: 2, 5: 1}


def test_an_empty_distribution_is_still_the_whole_scale():
    assert campaign_report.response_distribution([], *SCALE) == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}


# ------------------------------------------------------------------------ item summary


def test_an_item_summary_reads_the_campaign_not_the_course():
    summary = campaign_report.summarise_item([answers(4, 4), answers(2, 5), answers()], *SCALE)

    assert summary.scored_count == 4
    assert summary.average == 3.75
    assert summary.answered_contents == 2
    assert summary.agreement.pair_count == 2
    assert summary.distribution == {1: 0, 2: 1, 3: 0, 4: 2, 5: 1}


def test_the_three_silences_are_counted_apart():
    """Nobody asked · asked and could not judge · nobody has looked yet (ADR-0060 §4)."""
    summary = campaign_report.summarise_item(
        [answers(withheld=True), answers(4, abstentions=1), answers()], *SCALE
    )

    assert summary.withheld_contents == 1
    assert summary.abstentions == 1
    assert summary.answered_contents == 1
    # Nothing scored twice on one course, so there is no agreement to report.
    assert summary.agreement.pair_count == 0


def test_an_item_nobody_answered_has_a_null_average_never_a_zero():
    summary = campaign_report.summarise_item([answers(), answers(withheld=True)], *SCALE)

    assert summary.average is None
    assert summary.scored_count == 0
    assert summary.answered_contents == 0


def test_an_abstention_does_not_lower_an_average():
    with_abstention = campaign_report.summarise_item([answers(4, 4, abstentions=1)], *SCALE)
    without = campaign_report.summarise_item([answers(4, 4)], *SCALE)

    assert with_abstention.average == without.average == 4.0
    assert with_abstention.abstentions == 1


# ------------------------------------------------------------------ course disagreement


def test_a_course_reports_both_how_far_and_how_widely_the_panel_differed():
    # Item deltas: 0, 3, 1 → mean 4/3, max 3, two items contested.
    result = campaign_report.content_disagreement([[4, 4], [2, 5], [3, 4]])

    assert result.max_abs_diff == 3
    assert round(result.mean_abs_diff or 0, 3) == 1.333
    assert result.contested_items == 2


def test_a_course_with_one_assessor_has_no_disagreement_to_report():
    result = campaign_report.content_disagreement([[4], [5], []])

    assert result.mean_abs_diff is None
    assert result.max_abs_diff is None
    assert result.contested_items == 0
