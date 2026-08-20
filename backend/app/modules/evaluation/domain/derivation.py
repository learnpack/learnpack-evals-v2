"""Mechanical derivation of criterion outcomes — the automated path's core (13-code §3.5).

Per criterion, precedence order (each cause is the most upstream one — its remedy names
what to fix: better format/extraction · better generator · better assessor · better run):

(a) the instrument's bindings do not cover the profile's package format, or the
    criterion's `condition` excludes it under the binding's task variables
    -> `not_applicable` (derived)
(b) some required datum has NO entry in the profile — capability the adapter never
    declared -> `not_applicable` (derived; unmet demand for this format, ADR-0017)
(c) some required entry is an explicit `absent` -> `no_evidence`, or a derived `fail`
    when the criterion declares `on_missing_evidence='fail'` (the absence IS the defect,
    ADR-0009 §4 / ADR-0021 — quoteless, with a mechanical failure mode)
(d) the assessor abstains from the criterion -> `not_assessed` (derived; ADR-0018 —
    the datum is there and judgeable, this assessor declared it cannot judge it)
(e) otherwise -> the executor runs and its result becomes the scored outcome — or, when
    it raises the typed failure, `execution_error` with its cause (ADR-0037: a fact of
    this run, never of the content), bounded by the failure budget below

The invariant "non-scored outcomes are derived mechanically, never decided by the
assessor at runtime" holds by construction: abstentions are part of the assessor's
registered identity, executors only ever produce pass/fail, and an `execution_error` is
minted HERE from the failure the executor raised — raising is not deciding (ADR-0037 §1).

Exact coverage by construction: exactly one outcome per criterion of the snapshot.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeVar

from app.modules.evaluation.domain.model import (
    OUTCOME_EXECUTION_ERROR,
    OUTCOME_FAIL,
    OUTCOME_NO_EVIDENCE,
    OUTCOME_NOT_APPLICABLE,
    OUTCOME_NOT_ASSESSED,
    OUTCOME_PASS,
    ComputedMetric,
    Coverage,
    CriterionOutcome,
    CriterionSpec,
    ExecutionCause,
    ExecutionFailure,
    ExecutorResult,
    InstrumentSpec,
    InvalidAutomatedEvaluation,
    ProfileData,
)

Executor = Callable[[CriterionSpec, ProfileData], ExecutorResult]

_T = TypeVar("_T")
_R = TypeVar("_R")


class RunIndependently(Protocol):
    """Apply `work` to every item and answer in the SAME order.

    The criteria of one derivation are independent: each is decided from its own spec, the
    profile and the coverage, and none reads another's outcome. This is how the derivation
    SAYS so — and it is all it says. Whether anything happens at once, on threads, in another
    process or one after the next is the caller's business, and the answer must not differ
    either way.

    The mechanism is injected rather than chosen here because the domain has no business
    knowing it. An executor's work is minutes of network calls, and running several at once
    needs things this layer must not learn about: what carries a run's memoized answers, its
    trace sink and its cancellation token from one thread to the next. Those live in the
    infrastructure that owns them, so the implementation does too
    (`app/platform/concurrency.py`); the default below keeps this module correct on its own.
    """

    def __call__(self, work: Callable[[_T], _R], items: Sequence[_T]) -> Sequence[_R]: ...


def one_at_a_time[T, R](work: Callable[[T], R], items: Sequence[T]) -> Sequence[R]:
    """The default: each in turn, in order. Pure, and the whole contract satisfied."""
    return [work(item) for item in items]


# What one executable criterion answered. An executor may fail two ways and neither is
# raised through the runner: a typed `ExecutionFailure` is a fact of this run that the budget
# below may absorb, and an `InvalidAutomatedEvaluation` is a bug in the artifact that must
# propagate. Carrying them as VALUES is what keeps the runner's contract free of exception
# semantics — and what lets both be re-raised in criterion order rather than in whatever
# order the work happened to finish.
_Answer = ExecutorResult | ExecutionFailure | InvalidAutomatedEvaluation

# The failure budget (ADR-0037 §3): the proportion of the criteria mapped for execution
# that may carry `execution_error` before the evaluation is not worth persisting. Past it
# the original failure propagates and the run aborts whole, nothing persisted — ADR-0034
# §4 surviving as the limit case (an instrument with ≤3 executable criteria tolerates
# zero). A decision constant, reviewed like one; its effect is checkable because the
# failure counts travel with every evaluation.
EXECUTION_FAILURE_BUDGET = 0.25


def absence_failure_mode(missing: list[str]) -> str:
    """The mechanical failure mode of an absence-derived fail (ADR-0021)."""
    return f"required data absent: {', '.join(sorted(missing))}"


def derive_and_execute(
    instrument: InstrumentSpec,
    profile: ProfileData,
    coverage: Coverage,
    executors: Mapping[str, Executor],
    run: RunIndependently = one_at_a_time,
) -> tuple[tuple[CriterionOutcome, ...], tuple[ComputedMetric, ...]]:
    """One outcome per criterion of the snapshot; raw metrics from the executors.

    Causes (a)-(d) are decided here, in order and for free: they read declared facts and
    nothing else. Only (e) reaches an executor, and those go through `run` together — see
    `RunIndependently`. Whatever it does, the outcomes come back in the instrument's order.
    """
    format_covered = any(
        binding.package_format == profile.package_format for binding in instrument.bindings
    )
    binding_variables: Mapping[str, object] = next(
        (
            binding.task_variables
            for binding in instrument.bindings
            if binding.package_format == profile.package_format
        ),
        {},
    )

    executable = sum(
        1 for criterion in instrument.criteria if criterion.criterion_id in coverage.executes
    )
    allowed = int(EXECUTION_FAILURE_BUDGET * executable)

    # Everything decidable from declared facts, decided first. What is left over is the set
    # of criteria whose evidence has to be looked at.
    declared: list[tuple[CriterionOutcome, tuple[ComputedMetric, ...]] | None] = []
    judgeable: list[CriterionSpec] = []
    for criterion in instrument.criteria:
        early = _derive_without_judging(
            criterion, profile, coverage, format_covered, binding_variables
        )
        declared.append(early)
        if early is None:
            judgeable.append(criterion)

    answers = run(lambda criterion: _judge(criterion, profile, executors), judgeable)
    answered = dict(zip((c.criterion_id for c in judgeable), answers, strict=True))

    # Everything below is decided in the INSTRUMENT's order, over answers that are already
    # in. That is what keeps the outcome of a run independent of which executor happened to
    # finish first: the same answers always produce the same outcomes, the same budget
    # arithmetic, and the same exception out of the same criterion.
    outcomes: list[CriterionOutcome] = []
    metrics: dict[str, ComputedMetric] = {}
    failures = 0
    for criterion, early in zip(instrument.criteria, declared, strict=True):
        if early is not None:
            outcomes.append(early[0])
            for metric in early[1]:
                metrics[metric.metric_id] = metric
            continue
        answer = answered[criterion.criterion_id]
        if isinstance(answer, InvalidAutomatedEvaluation):
            # A bug in the artifact, never softened into an outcome and never absorbed by
            # the budget (ADR-0037 §1): it propagates on the first criterion that exposes it.
            raise answer
        if isinstance(answer, ExecutionFailure):
            failures += 1
            if failures > allowed:
                # Past the budget this was not an evaluation; the original failure
                # propagates and the run aborts whole (ADR-0037 §3). Counted in the
                # instrument's order, so the same run always fails on the same criterion.
                raise answer
            outcomes.append(
                CriterionOutcome(
                    criterion_id=criterion.criterion_id,
                    outcome=OUTCOME_EXECUTION_ERROR,
                    derived=True,
                    execution_cause=ExecutionCause(
                        task=answer.task, kind=answer.kind, message=str(answer)
                    ),
                )
            )
            continue
        scored = _scored(criterion, answer)
        outcomes.append(scored[0])
        for metric in scored[1]:
            metrics[metric.metric_id] = metric
    return tuple(outcomes), tuple(metrics.values())


def _judge(
    criterion: CriterionSpec, profile: ProfileData, executors: Mapping[str, Executor]
) -> _Answer:
    """(e) The executor looks at the evidence. Never raises what the caller must order."""
    executor = executors.get(criterion.criterion_id)
    if executor is None:
        return InvalidAutomatedEvaluation(
            f"criterion {criterion.criterion_id} is judgeable but the assessor maps no "
            "executor for it — its coverage does not match this instrument version "
            "(ratification should have caught this, ADR-0019)"
        )
    try:
        return executor(criterion, profile)
    except ExecutionFailure as exc:
        return exc


def _scored(
    criterion: CriterionSpec, result: ExecutorResult
) -> tuple[CriterionOutcome, tuple[ComputedMetric, ...]]:
    if not result.passed and result.failure_mode not in criterion.failure_modes:
        raise InvalidAutomatedEvaluation(
            f"criterion {criterion.criterion_id}: executor reported failure mode "
            f"{result.failure_mode!r}, which the criterion does not declare"
        )
    return (
        CriterionOutcome(
            criterion_id=criterion.criterion_id,
            outcome=OUTCOME_PASS if result.passed else OUTCOME_FAIL,
            derived=False,
            quote=result.quote,
            locator=result.locator,
            failure_mode=None if result.passed else result.failure_mode,
        ),
        result.metrics,
    )


def _derive_without_judging(
    criterion: CriterionSpec,
    profile: ProfileData,
    coverage: Coverage,
    format_covered: bool,
    binding_variables: Mapping[str, object],
) -> tuple[CriterionOutcome, tuple[ComputedMetric, ...]] | None:
    """Causes (a)-(d), or `None` when the criterion is judgeable and (e) has to run."""
    # (a) applicability: binding coverage + conditional criteria via task variables.
    if not format_covered or _condition_excludes(criterion, binding_variables):
        return _derived(criterion, OUTCOME_NOT_APPLICABLE), ()

    # (b) capability: a required datum with no entry at all — no adapter declared it.
    missing_capability = [
        datum for datum in criterion.required_data if datum not in profile.entries
    ]
    if missing_capability:
        return _derived(criterion, OUTCOME_NOT_APPLICABLE), ()

    # (c) absence: the adapter looked and there was nothing.
    absent = [datum for datum in criterion.required_data if profile.entries[datum].is_absent]
    if absent:
        if criterion.on_missing_evidence == "fail":
            return (
                CriterionOutcome(
                    criterion_id=criterion.criterion_id,
                    outcome=OUTCOME_FAIL,
                    derived=True,
                    failure_mode=absence_failure_mode(absent),
                ),
                (),
            )
        return _derived(criterion, OUTCOME_NO_EVIDENCE), ()

    # (d) abstention: registered with the assessor's identity, applied mechanically.
    if criterion.criterion_id in coverage.abstains:
        return _derived(criterion, OUTCOME_NOT_ASSESSED), ()

    # (e) judgeable: not decidable from declared facts. `_judge` looks at the evidence.
    return None


def _derived(criterion: CriterionSpec, outcome: str) -> CriterionOutcome:
    return CriterionOutcome(criterion_id=criterion.criterion_id, outcome=outcome, derived=True)


def _condition_excludes(criterion: CriterionSpec, binding_variables: Mapping[str, object]) -> bool:
    """A conditional criterion applies only when every named task variable matches.

    Minimal semantics for the first increment: `condition` is a mapping of task-variable
    name -> required value; no real criterion declares one yet (demand-driven)."""
    if not criterion.condition:
        return False
    return any(binding_variables.get(name) != value for name, value in criterion.condition.items())
