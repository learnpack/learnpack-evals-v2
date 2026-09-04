"""The arithmetic of a claim's validity (ADR-0063) — pure, no DB, no other module.

What is worth pinning here is not that the formulas are the formulas; it is the handful of
places where the honest answer is `None` or `unvalidated` and the tempting one is a number.
"""

from app.modules.reporting.application.claim_validity import (
    ABSENT,
    ACCEPT,
    GREY,
    REFUTED,
    REJECT,
    SUPPORTED,
    Confusion,
    Thresholds,
    Verdict,
    agreement,
    classify,
    cohen_kappa,
    confuse,
    discordant_cell,
    distance_from_cut,
    human_verdict,
    pairwise_agreement,
    rater_verdicts,
    sensitivity,
    specificity,
    verdicts_agree,
    youden_j,
)

# A table that separates well: 19 of 20 accepted are supported, 13 of 15 rejected are refuted.
# kappa 0.82, agreement 0.91.
TRACKING = Confusion(
    supported_accepted=19, refuted_accepted=1, supported_rejected=2, refuted_rejected=13
)

# 18 of 22 and 9 of 13 — the shape a reader calls "pretty good" at a glance, and it is NOT:
# kappa 0.51, under the bar. Kept as a fixture because the gap between how it reads and what
# it scores is the whole reason the bar is chance-corrected.
MIDDLING = Confusion(
    supported_accepted=18, refuted_accepted=4, supported_rejected=4, refuted_rejected=9
)


# ---- the cut (ADR-0063 §2)


def test_the_mean_of_the_raters_decides_the_side():
    assert human_verdict([4, 5]) == ACCEPT
    assert human_verdict([1, 2]) == REJECT


def test_the_middle_is_grey_and_is_neither_side():
    assert human_verdict([3, 3]) == GREY
    assert human_verdict([4, 2]) == GREY


def test_the_boundaries_belong_to_the_sides_they_name():
    assert human_verdict([4, 4]) == ACCEPT
    assert human_verdict([2, 2]) == REJECT


def test_no_scores_is_absent_not_grey():
    """Nobody answered is a different fact from the panel not committing."""
    assert human_verdict([]) == ABSENT


def test_the_cut_is_a_value():
    assert human_verdict([3], Thresholds(accept_at=3)) == ACCEPT


def test_each_rater_is_cut_on_their_own_for_the_ceiling():
    assert rater_verdicts([5, 2]) == [ACCEPT, REJECT]
    assert rater_verdicts([4, 3]) == [ACCEPT, GREY]


# ---- the 2x2


def test_only_clean_pairs_enter_the_table():
    c = confuse(
        [
            (ACCEPT, SUPPORTED),
            (REJECT, REFUTED),
            (GREY, SUPPORTED),  # the panel did not commit
            (ABSENT, REFUTED),  # nobody answered
            (ACCEPT, "insufficient"),  # the assessor did not commit
        ]
    )
    assert c.total == 2
    assert c.supported_accepted == 1
    assert c.refuted_rejected == 1


def test_sensitivity_and_specificity_carry_their_denominators():
    assert (sensitivity(MIDDLING).hit, sensitivity(MIDDLING).of) == (18, 22)
    assert (specificity(MIDDLING).hit, specificity(MIDDLING).of) == (9, 13)


def test_a_ratio_with_no_denominator_is_none_not_zero():
    """`0 %` would say the assessor missed everything; nothing was asked of it."""
    assert sensitivity(Confusion()).value is None


# ---- the coefficients


def test_youden_is_sensitivity_plus_specificity_minus_one():
    j = youden_j(MIDDLING)
    assert j is not None
    assert round(j, 3) == round(18 / 22 + 9 / 13 - 1, 3)


def test_youden_is_none_when_a_side_was_never_seen():
    assert youden_j(Confusion(supported_accepted=5, refuted_accepted=1)) is None


def test_kappa_is_none_on_an_empty_table():
    assert cohen_kappa(Confusion()) is None


def test_kappa_is_none_when_both_sides_always_said_the_same():
    """Expected agreement is 1, so the coefficient is undefined — not perfect."""
    assert cohen_kappa(Confusion(supported_accepted=12)) is None


def test_kappa_is_zero_at_chance_and_one_at_perfect():
    perfect = Confusion(supported_accepted=10, refuted_rejected=10)
    assert cohen_kappa(perfect) == 1.0
    # 10/10/10/10: observed .5, expected .5 — exactly what guessing would give.
    chance = Confusion(
        supported_accepted=10, refuted_accepted=10, supported_rejected=10, refuted_rejected=10
    )
    assert cohen_kappa(chance) == 0.0


def test_agreement_is_the_share_the_two_sides_landed_together():
    assert agreement(MIDDLING) == (18 + 9) / 35
    assert agreement(Confusion()) is None


# ---- the ceiling


def test_the_ceiling_pairs_raters_within_one_course():
    assert pairwise_agreement([[ACCEPT, ACCEPT], [REJECT, REJECT], [ACCEPT, REJECT]]) == 2 / 3


def test_a_grey_rater_contributes_no_pair():
    """The ceiling has to be measured on the same cut the judge is (ADR-0063 §4)."""
    assert pairwise_agreement([[ACCEPT, GREY], [ACCEPT, ACCEPT]]) == 1.0


def test_the_ceiling_is_none_when_no_course_produced_a_pair():
    assert pairwise_agreement([[ACCEPT], [GREY, GREY], []]) is None


# ---- the verdict


def test_a_claim_that_separates_and_agrees_tracks():
    assert classify(TRACKING, ceiling=0.95).status == "tracks"


def test_a_table_that_reads_well_can_still_miss_the_bar():
    """18 of 22 and 9 of 13 looks strong and scores kappa 0.51. That gap is why the bar is
    chance-corrected rather than a raw agreement."""
    assert classify(MIDDLING, ceiling=0.85) == Verdict("weak", "kappa_below_bar")


def test_too_few_courses_is_unvalidated_before_anything_else():
    tiny = Confusion(supported_accepted=3, refuted_rejected=3)
    assert classify(tiny, ceiling=0.9) == Verdict("unvalidated", "too_few")


def test_a_claim_the_experts_never_rejected_cannot_be_validated():
    """No number of raters fixes a claim that never distinguishes anything."""
    flat = Confusion(supported_accepted=18, refuted_accepted=4)
    assert classify(flat, ceiling=0.9) == Verdict("unvalidated", "no_variance")


def test_a_panel_that_disagrees_with_itself_leaves_nothing_to_validate_against():
    assert classify(TRACKING, ceiling=0.4) == Verdict("unvalidated", "ceiling_too_low")
    assert classify(TRACKING, ceiling=None) == Verdict("unvalidated", "ceiling_too_low")


def test_between_the_two_sample_bars_a_verdict_is_offered_but_never_tracks():
    small = Confusion(
        supported_accepted=6, refuted_accepted=0, supported_rejected=0, refuted_rejected=6
    )
    assert classify(small, ceiling=0.95) == Verdict("weak", "sample_below_tracking")


def test_low_kappa_is_weak_even_with_a_high_ceiling():
    noisy = Confusion(
        supported_accepted=10, refuted_accepted=8, supported_rejected=8, refuted_rejected=10
    )
    assert classify(noisy, ceiling=0.95) == Verdict("weak", "kappa_below_bar")


def test_falling_far_under_the_panel_is_weak_however_good_the_kappa():
    """The ETS relative rule: worse than a second expert is allowed, much worse is not.

    kappa 0.70 clears its own bar; the judge still agrees 13 points less often than the two
    experts agree with each other, and that is what the relative half is for.
    """
    solid = Confusion(
        supported_accepted=17, refuted_accepted=3, supported_rejected=3, refuted_rejected=17
    )
    assert classify(solid, ceiling=0.90).status == "tracks"
    assert classify(solid, ceiling=0.98) == Verdict("weak", "degrades_from_ceiling")


def test_the_bars_are_values():
    assert classify(MIDDLING, ceiling=0.85).status == "weak"
    assert classify(MIDDLING, ceiling=0.85, thresholds=Thresholds(min_kappa=0.5)).status == (
        "tracks"
    )


# ---- the discordant courses (ADR-0063 §9: shown, never corrected)


def test_only_the_two_off_diagonal_cells_are_a_disagreement():
    assert discordant_cell(ACCEPT, REFUTED) == "refuted_accepted"
    assert discordant_cell(REJECT, SUPPORTED) == "supported_rejected"
    assert discordant_cell(ACCEPT, SUPPORTED) is None
    assert discordant_cell(REJECT, REFUTED) is None


def test_an_absence_is_not_a_disagreement():
    """The grey zone, the unanswered item and the assessor's `insufficient` never clash.

    They are courses where one of the two sides declined to commit, which is the same reason
    `confuse` leaves them out of the 2x2 — counting them as contradictions would invent a
    disagreement nobody had.
    """
    assert discordant_cell(GREY, REFUTED) is None
    assert discordant_cell(ABSENT, SUPPORTED) is None
    assert discordant_cell(ACCEPT, "insufficient") is None


def test_the_widest_disagreement_is_the_one_furthest_past_the_cut():
    """A course rejected at 1.0 contradicts the assessor harder than one rejected at 2.0."""
    assert distance_from_cut(1.0) > distance_from_cut(2.0)
    assert distance_from_cut(5.0) > distance_from_cut(4.0)
    assert distance_from_cut(4.0) == 0.0


def test_a_course_inside_the_grey_zone_is_at_no_distance():
    assert distance_from_cut(3.0) == 0.0


def test_the_distance_moves_with_the_cut_because_the_cut_is_a_value():
    assert distance_from_cut(3.0, Thresholds(accept_at=3)) == 0.0
    assert distance_from_cut(4.0, Thresholds(accept_at=3)) == 1.0


def test_two_experts_on_the_same_side_agree_and_on_opposite_sides_do_not():
    assert verdicts_agree([ACCEPT, ACCEPT]) is True
    assert verdicts_agree([ACCEPT, REJECT]) is False


def test_one_opinion_is_not_a_disagreement_with_itself():
    """`None`, never `False`: a single expert cannot fail to agree with a second one.

    The distinction matters where a reader is about to blame the reference item — that
    diagnosis needs two people who read the same course differently, not one who read it.
    """
    assert verdicts_agree([ACCEPT]) is None
    assert verdicts_agree([]) is None


def test_an_expert_in_the_grey_zone_takes_no_side():
    """Same rule as the ceiling: grey is not a side, so it forms no pair (ADR-0063 §4)."""
    assert verdicts_agree([ACCEPT, GREY]) is None
    assert verdicts_agree([ACCEPT, GREY, ACCEPT]) is True
