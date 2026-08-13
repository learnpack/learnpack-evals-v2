"""The one failure every automated assessor can raise at runtime (ADR-0037).

An executor produces `pass` or `fail`, never anything else — the non-scored outcomes are
derived mechanically before it runs (ADR-0016/0018). When an assessor genuinely cannot
produce a verdict, it raises this: raising is not deciding an outcome, so the derivation
is what turns the failure into `execution_error` for the criteria the failed task feeds,
bounded by the failure budget — past the budget the evaluation still aborts whole and
nothing persists (ADR-0034 §4 surviving as the limit case).

`kind` is what the retry policy and the recorded cause read (ADR-0037 §7): `transport` ·
`configuration` · `response` (the platform client's own taxonomy, preserved instead of
collapsed) · `budget` (`finish_reason: length`) · `contract` (the schema/grounding budget
spent) · `degeneration` (verbatim repetition — the one kind a clean-conversation retry may
buy back) · `profile` (a broken package, not a finding about its pedagogy).

This module is deliberately tiny and shared: it is error plumbing, not semantics, so it is
not part of any assessor's identity (ADR-0034) — the same reasoning that shares the
transport client. Everything semantic stays duplicated per assessor package.
"""

from app.modules.evaluation.domain.model import ExecutionFailure


class AssessorExecutionError(ExecutionFailure):
    """The assessor could not judge; the derivation decides what that costs (ADR-0037)."""
