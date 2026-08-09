"""One policy subscription list, shared by every process that runs use cases.

The dispatcher is a module-level singleton and each process wires it at boot: the API in
`main.py`, the CLI in `cli.py`. Two lists drifted once — the CLI subscribed only the
evaluation policy, so `register-package` never auto-profiled while the admin form did — and
nothing could catch it: a missing subscription is indistinguishable from an event nobody
cares about. There is one list now (ADR-0029 §1).

It lives under `platform/` because the composition root is the only place allowed to name
another module's `infrastructure` (ARCHITECTURE.md §3, pinned by `tests/test_architecture.py`).
An `app/policies.py` would fail that test.

Import direction, deliberately one-way: this module imports `platform.events` and every
module's policies; nothing in `platform/` imports THIS. `platform/__init__.py` is empty and
must stay empty, or `uow -> policies -> module infrastructure -> uow` closes a cycle.

The chain (08-code.md §5 - 13-code-qa.md §5):
  EvaluationSubmitted        -> (orchestration) ContentEvaluationCompleted
  ContentEvaluationCompleted -> (golden)        GoldenReferenceEstablished
  ContentVersionRegistered   -> (profiling)     profile, if the extraction is accepted
  EvaluationCompleted        -> (evaluation)    derive the QualityJudgment + findings

Swapping the in-process dispatcher for a real bus later touches only this function.
"""

from app.modules.content_profiling.infrastructure.policies import (
    register_policies as register_profiling_policies,
)
from app.modules.evaluation.infrastructure.policies import (
    register_policies as register_evaluation_policies,
)
from app.modules.golden_dataset.infrastructure.policies import (
    register_policies as register_golden_policies,
)
from app.modules.orchestration.infrastructure.policies import (
    register_policies as register_orchestration_policies,
)
from app.platform.events import EventDispatcher


def register_all_policies(dispatcher: EventDispatcher) -> None:
    """Subscribe every policy of the system. Every process calls exactly this.

    Takes the dispatcher as an argument rather than reaching for the singleton, so a test
    can assert the whole chain on a fresh one — on the singleton it cannot, since importing
    `app.main` has already wired it by the time any test runs.
    """
    register_orchestration_policies(dispatcher)
    register_golden_policies(dispatcher)
    register_profiling_policies(dispatcher)
    register_evaluation_policies(dispatcher)
