"""The one failure every automated assessor can raise at runtime (ADR-0034 clause 4).

An executor produces `pass` or `fail`, never anything else — the non-scored outcomes are
derived mechanically before it runs (ADR-0016/0018). So when an assessor genuinely cannot
produce a verdict (an LLM's retry budget spent on transport failures, schema violations or
ungrounded quotes), the honest move is not a new outcome: it is aborting the evaluation
whole, the same all-or-nothing shape the extraction path has (`ExtractionError` → a
`failed` profile, never a half-profile). Nothing persists; retrying is running `evaluate`
again.

This module is deliberately tiny and shared: it is error plumbing, not semantics, so it is
not part of any assessor's identity (ADR-0034) — the same reasoning that shares the
transport client. Everything semantic stays duplicated per assessor package.
"""


class AssessorExecutionError(Exception):
    """The assessor could not produce a verdict; the evaluation aborts, nothing persists."""
