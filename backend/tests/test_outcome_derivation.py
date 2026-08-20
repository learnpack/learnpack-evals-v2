"""Mechanical six-state derivation — pure domain, no DB (13-code §10).

Case table: capability × absence × on_missing_evidence × condition × abstention ×
binding coverage, plus the mixed multi-required cases, the failure budget (ADR-0037) and
exact coverage by construction.
"""

from uuid import uuid4

import pytest

from app.modules.evaluation.domain.derivation import (
    EXECUTION_FAILURE_BUDGET,
    absence_failure_mode,
    derive_and_execute,
)
from app.modules.evaluation.domain.model import (
    BindingSpec,
    ClaimSpec,
    ComputedMetric,
    Coverage,
    CriterionSpec,
    ExecutionFailure,
    ExecutorResult,
    InstrumentSpec,
    InvalidAutomatedEvaluation,
    ProfileData,
    ProfileEntryData,
)


def criterion(criterion_id="cr-x", **overrides) -> CriterionSpec:
    base = dict(
        criterion_id=criterion_id,
        pass_condition="something verifiable",
        failure_modes=("declared mode",),
        claim_ids=("cl-1",),
        required_data=("datum",),
    )
    return CriterionSpec(**(base | overrides))


def instrument(*criteria: CriterionSpec, bindings=None) -> InstrumentSpec:
    return InstrumentSpec(
        instrument_version_id="qa-v1",
        instrument_id="qa",
        status="published",
        claims=(ClaimSpec(claim_id="cl-1"),),
        criteria=criteria,
        bindings=bindings if bindings is not None else (BindingSpec("LearnpackV1"),),
    )


def profile(entries: dict[str, ProfileEntryData], package_format="LearnpackV1") -> ProfileData:
    return ProfileData(profile_id=uuid4(), package_format=package_format, entries=entries)


def declared(datum="datum", value="the value") -> ProfileEntryData:
    return ProfileEntryData(
        data_requirement_id=datum,
        provenance="declared_structured",
        value=value,
        quote="the quote",
        locator={"artifact": "learn.json"},
    )


def absent(datum="datum") -> ProfileEntryData:
    return ProfileEntryData(data_requirement_id=datum, provenance="absent")


def passing_executor(spec, prof) -> ExecutorResult:
    return ExecutorResult(passed=True, quote="seen in the content")


NO_COVERAGE = Coverage(executes=frozenset(), abstains={})


def run(instr, prof, coverage=None, executors=None):
    return derive_and_execute(
        instr,
        prof,
        coverage if coverage is not None else Coverage(frozenset({"cr-x"}), {}),
        executors if executors is not None else {"cr-x": passing_executor},
    )


# --- (a) applicability ------------------------------------------------------------


def test_uncovered_package_format_derives_not_applicable_for_every_criterion():
    outcomes, _ = run(instrument(criterion()), profile({"datum": declared()}, "OtherFormat"))
    assert [(o.outcome, o.derived) for o in outcomes] == [("not_applicable", True)]


def test_condition_excluded_by_task_variables_derives_not_applicable():
    instr = instrument(
        criterion(condition={"courseKind": "full"}),
        bindings=(BindingSpec("LearnpackV1", {"courseKind": "fragment"}),),
    )
    outcomes, _ = run(instr, profile({"datum": declared()}))
    assert outcomes[0].outcome == "not_applicable"


def test_condition_satisfied_reaches_the_executor():
    instr = instrument(
        criterion(condition={"courseKind": "full"}),
        bindings=(BindingSpec("LearnpackV1", {"courseKind": "full"}),),
    )
    outcomes, _ = run(instr, profile({"datum": declared()}))
    assert outcomes[0].outcome == "pass"


# --- (b) capability ---------------------------------------------------------------


def test_required_datum_without_entry_derives_not_applicable():
    outcomes, _ = run(instrument(criterion()), profile({}))
    assert [(o.outcome, o.derived) for o in outcomes] == [("not_applicable", True)]


def test_capability_beats_absence_in_the_mixed_multi_required_case():
    # One required datum has no entry (no capability), the other is absent:
    # the most upstream cause wins — not_applicable, never a derived fail.
    spec = criterion(required_data=("covered", "uncovered"), on_missing_evidence="fail")
    outcomes, _ = run(instrument(spec), profile({"covered": absent("covered")}))
    assert outcomes[0].outcome == "not_applicable"


# --- (c) absence ------------------------------------------------------------------


def test_absent_entry_derives_no_evidence_by_default():
    outcomes, _ = run(instrument(criterion()), profile({"datum": absent()}))
    assert [(o.outcome, o.derived) for o in outcomes] == [("no_evidence", True)]


def test_absent_entry_with_on_missing_fail_derives_a_quoteless_fail():
    outcomes, _ = run(
        instrument(criterion(on_missing_evidence="fail")), profile({"datum": absent()})
    )
    outcome = outcomes[0]
    assert outcome.outcome == "fail"
    assert outcome.derived is True
    assert outcome.quote is None  # ADR-0021: the absence IS the defect
    assert outcome.failure_mode == absence_failure_mode(["datum"])


def test_absence_beats_abstention():
    # Abstention means "the datum is there and I cannot judge it" — with the datum
    # absent, the abstention is irrelevant (ADR-0018 §2).
    outcomes, _ = run(
        instrument(criterion()),
        profile({"datum": absent()}),
        coverage=Coverage(frozenset(), {"cr-x": "semantic judgment"}),
        executors={},
    )
    assert outcomes[0].outcome == "no_evidence"


# --- (d) abstention ---------------------------------------------------------------


def test_abstained_criterion_derives_not_assessed():
    outcomes, _ = run(
        instrument(criterion()),
        profile({"datum": declared()}),
        coverage=Coverage(frozenset(), {"cr-x": "requires semantic judgment"}),
        executors={},
    )
    assert [(o.outcome, o.derived) for o in outcomes] == [("not_assessed", True)]


# --- (e) execution ----------------------------------------------------------------


def test_executed_pass_carries_the_quote():
    outcomes, _ = run(instrument(criterion()), profile({"datum": declared()}))
    outcome = outcomes[0]
    assert (outcome.outcome, outcome.derived) == ("pass", False)
    assert outcome.quote == "seen in the content"


def test_executed_fail_carries_quote_and_declared_failure_mode():
    def failing(spec, prof):
        return ExecutorResult(
            passed=False, quote="the offending text", failure_mode="declared mode"
        )

    outcomes, _ = run(
        instrument(criterion()), profile({"datum": declared()}), executors={"cr-x": failing}
    )
    outcome = outcomes[0]
    assert (outcome.outcome, outcome.quote) == ("fail", "the offending text")
    assert outcome.failure_mode == "declared mode"


def test_executor_reporting_an_undeclared_failure_mode_is_rejected():
    def failing(spec, prof):
        return ExecutorResult(passed=False, quote="text", failure_mode="invented mode")

    with pytest.raises(InvalidAutomatedEvaluation, match="does not declare"):
        run(instrument(criterion()), profile({"datum": declared()}), executors={"cr-x": failing})


def test_judgeable_criterion_without_executor_is_a_coverage_error():
    with pytest.raises(InvalidAutomatedEvaluation, match="ratification"):
        run(
            instrument(criterion()),
            profile({"datum": declared()}),
            coverage=NO_COVERAGE,
            executors={},
        )


def test_executor_metrics_are_collected():
    def measuring(spec, prof):
        return ExecutorResult(passed=True, quote="q", metrics=(ComputedMetric("lesson_count", 7),))

    _, metrics = run(
        instrument(criterion()), profile({"datum": declared()}), executors={"cr-x": measuring}
    )
    assert metrics == (ComputedMetric("lesson_count", 7),)


# --- (e) execution failure: the budget (ADR-0037) ---------------------------------


def raising_executor(spec, prof):
    raise ExecutionFailure("task 'probe': the model looped", kind="degeneration", task="probe")


def test_a_failure_under_the_budget_becomes_execution_error_with_its_cause():
    """Five executable criteria tolerate one failure (int(0.25 * 5) = 1): the failed one
    carries the cause, the others persist, and the successes keep their metrics."""

    def measuring(spec, prof):
        return ExecutorResult(passed=True, quote="q", metrics=(ComputedMetric("count", 1),))

    ids = [f"cr-{i}" for i in range(5)]
    instr = instrument(*(criterion(cid) for cid in ids))
    executors = {cid: measuring for cid in ids} | {"cr-2": raising_executor}

    outcomes, metrics = run(
        instr,
        profile({"datum": declared()}),
        coverage=Coverage(frozenset(ids), {}),
        executors=executors,
    )

    by_id = {o.criterion_id: o for o in outcomes}
    errored = by_id["cr-2"]
    assert errored.outcome == "execution_error" and errored.derived
    assert errored.execution_cause.task == "probe"
    assert errored.execution_cause.kind == "degeneration"
    assert "the model looped" in errored.execution_cause.message
    assert [by_id[cid].outcome for cid in ids if cid != "cr-2"] == ["pass"] * 4
    assert metrics == (ComputedMetric("count", 1),)  # the successes' spend survives


def test_past_the_budget_the_original_failure_propagates_and_nothing_half_derives():
    """int(0.25 * 5) = 1 tolerated: the second failure re-raises the executor's own
    exception — ADR-0034 §4 surviving as the limit case."""
    ids = [f"cr-{i}" for i in range(5)]
    instr = instrument(*(criterion(cid) for cid in ids))
    executors = {cid: passing_executor for cid in ids} | {
        "cr-1": raising_executor,
        "cr-3": raising_executor,
    }

    with pytest.raises(ExecutionFailure, match="the model looped"):
        run(
            instr,
            profile({"datum": declared()}),
            coverage=Coverage(frozenset(ids), {}),
            executors=executors,
        )


def test_a_small_instrument_tolerates_zero_failures():
    """int(0.25 * 1) = 0: the budget's zero point IS the old all-or-nothing behavior."""
    assert EXECUTION_FAILURE_BUDGET == 0.25  # a decision constant; changing it is reviewed
    with pytest.raises(ExecutionFailure):
        run(
            instrument(criterion()),
            profile({"datum": declared()}),
            executors={"cr-x": raising_executor},
        )


def test_a_registration_bug_is_never_softened_into_an_execution_error():
    """`InvalidAutomatedEvaluation` (an executor reporting an undeclared failure mode, a
    missing executor) is a bug in the artifact, not a fact of the run: it propagates even
    when the budget would have absorbed a typed failure."""

    def failing(spec, prof):
        return ExecutorResult(passed=False, quote="text", failure_mode="invented mode")

    ids = [f"cr-{i}" for i in range(5)]
    instr = instrument(*(criterion(cid) for cid in ids))
    executors = {cid: passing_executor for cid in ids} | {"cr-2": failing}

    with pytest.raises(InvalidAutomatedEvaluation, match="does not declare"):
        run(
            instr,
            profile({"datum": declared()}),
            coverage=Coverage(frozenset(ids), {}),
            executors=executors,
        )


# --- exact coverage ---------------------------------------------------------------


def test_one_outcome_per_criterion_of_the_snapshot():
    instr = instrument(
        criterion("cr-a"),
        criterion("cr-b", required_data=("other",)),
        criterion("cr-c", on_missing_evidence="fail", required_data=("gone",)),
    )
    prof = profile({"datum": declared(), "gone": absent("gone")})
    outcomes, _ = run(
        instr,
        prof,
        coverage=Coverage(frozenset({"cr-a"}), {}),
        executors={"cr-a": passing_executor},
    )
    assert [o.criterion_id for o in outcomes] == ["cr-a", "cr-b", "cr-c"]
    assert [o.outcome for o in outcomes] == ["pass", "not_applicable", "fail"]


def test_coverage_overlap_is_rejected():
    with pytest.raises(InvalidAutomatedEvaluation, match="disjoint"):
        Coverage(frozenset({"cr-x"}), {"cr-x": "also abstained"})


# --- the runner: what the derivation delegates, and what it keeps (ADR-0048) -------


def test_only_the_judgeable_criteria_reach_the_runner():
    """Causes (a)-(d) are decided from declared facts and never cost a call, so a criterion
    the format cannot feed or the assessor abstains from must not be handed over."""
    handed: list[str] = []

    def watching(work, items):
        handed.extend(c.criterion_id for c in items)
        return [work(item) for item in items]

    instr = instrument(
        criterion("cr-judged"),
        criterion("cr-abstained"),
        criterion("cr-no-capability", required_data=("nobody-declares-this",)),
    )
    outcomes, _ = derive_and_execute(
        instr,
        profile({"datum": declared()}),
        Coverage(frozenset({"cr-judged"}), {"cr-abstained": "cannot judge it"}),
        {"cr-judged": passing_executor},
        watching,
    )

    assert handed == ["cr-judged"]
    assert [o.outcome for o in outcomes] == ["pass", "not_assessed", "not_applicable"]


def test_the_outcomes_are_in_the_instruments_order_whatever_the_runner_does():
    """The runner may do the work in any order — that is the whole point of delegating it —
    so the derivation must not read anything into the order it comes back in."""

    def backwards(work, items):
        # Done last-first, answered first-last: the contract is about the ANSWERS' order.
        done = {index: work(item) for index, item in reversed(list(enumerate(items)))}
        return [done[index] for index in range(len(items))]

    def quoting(spec, prof) -> ExecutorResult:
        return ExecutorResult(passed=True, quote=f"seen for {spec.criterion_id}")

    ids = [f"cr-{i}" for i in range(4)]
    instr = instrument(*(criterion(cid) for cid in ids))
    outcomes, _ = derive_and_execute(
        instr,
        profile({"datum": declared()}),
        Coverage(frozenset(ids), {}),
        {cid: quoting for cid in ids},
        backwards,
    )

    assert [o.criterion_id for o in outcomes] == ids
    assert [o.quote for o in outcomes] == [f"seen for {cid}" for cid in ids]


def test_the_budget_fails_on_the_same_criterion_however_the_work_was_ordered():
    """Which failure aborts a run is decided in the instrument's order, over answers that are
    already in — so a run that dies does not die differently depending on scheduling."""

    def backwards(work, items):
        done = {index: work(item) for index, item in reversed(list(enumerate(items)))}
        return [done[index] for index in range(len(items))]

    def failing(task: str):
        def executor(spec, prof) -> ExecutorResult:
            raise ExecutionFailure(f"{task} gave up", task=task, kind="degeneration")

        return executor

    ids = [f"cr-{i}" for i in range(5)]  # int(0.25 * 5) = 1 tolerated
    instr = instrument(*(criterion(cid) for cid in ids))
    executors = {cid: passing_executor for cid in ids} | {
        "cr-1": failing("first"),
        "cr-3": failing("second"),
    }

    with pytest.raises(ExecutionFailure, match="second gave up"):
        derive_and_execute(
            instr,
            profile({"datum": declared()}),
            Coverage(frozenset(ids), {}),
            executors,
            backwards,
        )
