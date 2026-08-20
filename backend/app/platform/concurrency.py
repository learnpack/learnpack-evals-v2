"""Doing independent work at once — the mechanism, for callers that only know the policy.

The domain says which units are independent and asks for the answers in order
(`RunIndependently`, `evaluation/domain/derivation.py`); this is the implementation that
makes them happen together. Keeping the two apart is the point: running work concurrently
here needs three things the domain must never learn about, and all three live in this layer.

Every worker runs inside a COPY of the caller's context, and that is the whole reason this
module exists rather than a bare `pool.map` at the call site. A fresh thread starts with an
empty context, and what a run carries in `ContextVar`s is exactly what it cannot afford to
lose: the assessor's memoized answers (`assessors/*/memo.py`) — without them each worker
re-asks and re-pays for questions the others already asked — the trace sink
(`observability.py`), whose absence once left the most expensive task in an evaluation with
no record of what it asked, and the cancellation token (`cancellation.py`), whose absence
means Ctrl-C stops the caller and not the work.

One copy per item, never one shared: a `Context` cannot be entered from two threads at once.

Not to be confused with the batch's own pool (`batch_runs.py`), which deliberately does NOT
copy context — two courses evaluated together must share no memoized answer, or two repeats
of one content stop being two samples. Same layer, opposite requirement, and both stated
where a reader can compare them.
"""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context, copy_context


def all_at_once[T, R](work: Callable[[T], R], items: Sequence[T]) -> Sequence[R]:
    """Apply `work` to every item together; answer in the order the items came in.

    No cap here on purpose. What bounds the requests this releases is the transport's own
    semaphore (`LLM_MAX_CONCURRENCY`, one per process), which is the only place that sees
    every call however many levels of fan-out sit above it — a batch over courses, then this
    over criteria, then a task over modules. A cap per level would not compose, and nobody
    would have decided the product of the three.

    A thread per item is not a cost worth managing: they are cheap, and a thread waiting on
    that semaphore is asking for nothing.
    """
    work_items = list(items)
    if len(work_items) < 2:
        return [work(item) for item in work_items]

    carried: list[tuple[Context, T]] = [(copy_context(), item) for item in work_items]
    with ThreadPoolExecutor(max_workers=len(work_items)) as pool:
        # `pool.map` yields in submission order, which is the contract's own promise: what
        # finished first is not something a caller of this module can observe.
        return list(pool.map(lambda pair: pair[0].run(work, pair[1]), carried))
