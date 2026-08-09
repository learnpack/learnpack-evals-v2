"""One subscription list, every process (ADR-0029 §1).

Asserted on a FRESH dispatcher, never the module singleton: two test modules do a top-level
`import app.main`, and pytest imports every module at collection, so by the time any test
runs the singleton already carries the whole chain. A second wiring would be
indistinguishable from the first — which is exactly why the CLI could drift unnoticed.

No database: these run on every `pytest`, like the architecture rules they sit beside.
"""

import pathlib

from app.platform.events import EventDispatcher
from app.platform.policies import register_all_policies

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# event type -> the module whose policy owns it. Adding a policy without adding it here
# fails, which is the point: this is the list, not a sample of it.
EXPECTED_OWNERS = {
    "EvaluationSubmitted": "app.modules.orchestration.infrastructure.policies",
    "ContentEvaluationCompleted": "app.modules.golden_dataset.infrastructure.policies",
    "ContentVersionRegistered": "app.modules.content_profiling.infrastructure.policies",
    "EvaluationCompleted": "app.modules.evaluation.infrastructure.policies",
}


def test_register_all_policies_subscribes_the_whole_chain():
    dispatcher = EventDispatcher()
    register_all_policies(dispatcher)

    owners = {
        event_type: [handler.__module__ for handler in handlers]
        for event_type, handlers in dispatcher.subscriptions().items()
    }
    assert owners == {event_type: [module] for event_type, module in EXPECTED_OWNERS.items()}


def test_neither_process_wires_policies_by_hand():
    """A second list is exactly how the CLI drifted from the API: it subscribed only the
    evaluation policy, so `register-package` never auto-profiled while the admin form did.
    Both entry points go through the shared function or this fails."""
    violations = []
    for name in ("main.py", "cli.py"):
        source = (APP / name).read_text(encoding="utf-8")
        if "register_all_policies(dispatcher)" not in source:
            violations.append(f"{name} does not call register_all_policies(dispatcher)")
        if "infrastructure.policies" in source:
            violations.append(f"{name} names a module's policies directly")

    assert not violations, "Policy wiring must be shared (ADR-0029 §1):\n" + "\n".join(violations)
