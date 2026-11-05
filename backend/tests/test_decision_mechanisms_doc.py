"""`docs/MEASUREMENT.md` says how each criterion is decided, and this test holds it to the code.

The tables in "How each criterion is decided" are reference: true of `main`, updated in the
same commit as the code that would make them false. A table that lists every criterion of an
instrument goes stale the first time an assessor version moves, and nothing in a review makes
that visible — so the tables are recomputed here and compared, cell by cell.

What is recomputed, and from where:

- **Which criteria an assessor executes or abstains from** — its declared coverage
  (`AUTOMATED_ASSESSORS`), intersected with the instrument version the workbench publishes for
  its lineage (`docs/seed/workbench.yaml`).
- **How an executed criterion is decided** — read off the code, never off its comments. The
  executor's call graph inside its assessor package is walked statically: an executor that
  reaches no call to the model is `deterministic`; one that reaches a call where the model
  answers with the verdict is `model judges`; any other call to the model is extraction,
  classification or mapping, and the verdict is code's (`model extracts, code decides`).
- **Whether it runs on a LearnpackV1 course** — the derivation's own rule (ADR-0018): the
  instrument binds the format, the binding's task variables satisfy the criterion's
  condition, and the V1 adapter declares every datum the criterion requires.

The one thing that cannot be read off the code is which calls to the model ask for a verdict.
`MODEL_CALLS` names every function that calls the model, and which kind it is. A new one
fails here until somebody decides — which is the point: it is exactly the question the
document answers.
"""

import ast
import inspect
import pathlib
import re
import types
from collections.abc import Iterator
from typing import Any

import yaml

from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS, AssessorPackage
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    structured_output,
)

REPO = pathlib.Path(__file__).resolve().parents[2]
MEASUREMENT = REPO / "docs" / "MEASUREMENT.md"
SEED = REPO / "docs" / "seed"

SECTION = "## How each criterion is decided"

DETERMINISTIC = "deterministic"
EXTRACTS = "model extracts, code decides"
JUDGES = "model judges"
ABSTAINS = "abstains"

RUNS = "runs"
NOT_APPLICABLE = "not applicable"

# The terminal of every call to a model: whatever reaches it spends a request.
MODEL_CALL = structured_output.request_structured_output

# Every function that calls the model directly, by qualified name, and what the model answers
# there. `JUDGES` = the answer carries the verdict (voted on in code, but the model's);
# `EXTRACTS` = the answer is data, and the pass condition is applied to it in code.
MODEL_CALLS = {
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.tasks.outcomes_extraction": (
        EXTRACTS
    ),
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.tasks.objectives_classification": (  # noqa: E501
        EXTRACTS
    ),
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.tasks.concept_trajectory": (
        EXTRACTS
    ),
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.tasks.concept_map": EXTRACTS,
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.judgments.assessment_mapping": (
        EXTRACTS
    ),
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.judgments.assessment_reach": (
        EXTRACTS
    ),
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.judgments._ask": JUDGES,
    "app.modules.evaluation.infrastructure.assessors.drafts_hybrid.judgments._ask_per_objective": (
        JUDGES
    ),
}


# --- reading the code -----------------------------------------------------------------------


def _qualname(obj: Any) -> str | None:
    if inspect.isfunction(obj):
        return f"{obj.__module__}.{obj.__name__}"
    return None


def _package_modules(package: AssessorPackage) -> list[types.ModuleType]:
    """Every module of the assessor's own package, imported."""
    executors_module = inspect.getmodule(next(iter(package.executors.values())))
    assert executors_module is not None
    package_name = executors_module.__name__.rsplit(".", 1)[0]
    package_dir = pathlib.Path(inspect.getfile(executors_module)).parent
    modules = []
    for path in sorted(package_dir.glob("*.py")):
        name = package_name if path.stem == "__init__" else f"{package_name}.{path.stem}"
        modules.append(__import__(name, fromlist=["_"]))
    return modules


def _references(module: types.ModuleType, node: ast.AST) -> Iterator[str]:
    """Qualified names of the functions `node` mentions — called or passed, nested or not.

    Resolved through the module's own globals, so an import alias resolves to what it names.
    Over-approximates on purpose: a function handed to a pool or a memo is reached too.
    """
    for child in ast.walk(node):
        target: Any = None
        if isinstance(child, ast.Name):
            target = module.__dict__.get(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
            owner = module.__dict__.get(child.value.id)
            if isinstance(owner, types.ModuleType):
                target = owner.__dict__.get(child.attr)
        name = _qualname(target)
        if name is not None:
            yield name


def _call_graph(package: AssessorPackage) -> dict[str, set[str]]:
    """Function -> the functions it reaches directly, for every top-level function."""
    graph: dict[str, set[str]] = {}
    for module in _package_modules(package):
        tree = ast.parse(inspect.getsource(module))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                graph[f"{module.__name__}.{node.name}"] = set(_references(module, node))
    return graph


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, ()))
    return seen


def _mechanisms(package: AssessorPackage) -> dict[str, str]:
    """Executed criterion -> how its executor decides, read off the call graph."""
    graph = _call_graph(package)
    model_call = _qualname(MODEL_CALL)
    reached_by_executor = {
        name: _reachable(graph, name)
        for name in (_qualname(executor) for executor in package.executors.values())
        if name is not None
    }
    # Only what an executor can reach: a package also carries calibration tooling that asks
    # the model outside any evaluation, and that decides no criterion.
    callers = {
        name
        for reached in reached_by_executor.values()
        for name in reached
        if model_call in graph.get(name, ())
    }
    undeclared = callers - MODEL_CALLS.keys()
    assert not undeclared, (
        f"{package.display_name} calls the model from {sorted(undeclared)}: add each to "
        "MODEL_CALLS as EXTRACTS or JUDGES — does the model answer with data, or with the verdict?"
    )

    mechanisms = {}
    for criterion_id, executor in package.executors.items():
        executor_name = _qualname(executor)
        assert executor_name is not None
        kinds = {MODEL_CALLS[name] for name in reached_by_executor[executor_name] & callers}
        if JUDGES in kinds:
            mechanisms[criterion_id] = JUDGES
        elif kinds:
            mechanisms[criterion_id] = EXTRACTS
        else:
            mechanisms[criterion_id] = DETERMINISTIC
    return mechanisms


def _published_instruments() -> dict[str, dict]:
    """Lineage -> the instrument version the workbench publishes for it."""
    workbench = yaml.safe_load((SEED / "workbench.yaml").read_text(encoding="utf-8"))
    published = {}
    for relative in workbench["instruments"]:
        spec = yaml.safe_load((SEED / relative).read_text(encoding="utf-8"))
        published[spec["instrument_id"]] = spec
    return published


def _version_id(spec: dict) -> str:
    return f"{spec['instrument_id']}-{spec['version']}"


def _expected_decisions(package: AssessorPackage, spec: dict) -> dict[str, str]:
    """Criterion of the published version -> how this assessor decides it."""
    mechanisms = _mechanisms(package)
    decisions = {}
    for criterion in spec["criteria"]:
        criterion_id = criterion["id"]
        if criterion_id in mechanisms:
            decisions[criterion_id] = mechanisms[criterion_id]
        else:
            assert criterion_id in package.coverage.abstains, (
                f"{package.display_name} neither executes nor abstains from {criterion_id}"
            )
            decisions[criterion_id] = ABSTAINS
    return decisions


def _on_learnpack_v1(spec: dict) -> dict[str, str]:
    """Criterion -> whether the derivation lets it run on a LearnpackV1 course (ADR-0018)."""
    binding = next(
        (b for b in spec["bindings"] if b["package_format"] == "LearnpackV1"),
        None,
    )
    capabilities = ADAPTERS_BY_FORMAT["LearnpackV1"].capabilities
    on_v1 = {}
    for criterion in spec["criteria"]:
        variables = (binding or {}).get("task_variables") or {}
        condition = criterion.get("condition") or {}
        runs = (
            binding is not None
            and all(variables.get(name) == value for name, value in condition.items())
            and set(criterion["requires"]) <= capabilities
        )
        on_v1[criterion["id"]] = RUNS if runs else NOT_APPLICABLE
    return on_v1


# --- reading the document -------------------------------------------------------------------


def _section() -> str:
    text = MEASUREMENT.read_text(encoding="utf-8")
    assert SECTION in text, f"docs/MEASUREMENT.md has no '{SECTION}' section"
    body = text.split(SECTION, 1)[1]
    return re.split(r"^## ", body, maxsplit=1, flags=re.M)[0]


def _table_after(text: str, heading_pattern: str) -> tuple[re.Match[str], list[list[str]]]:
    """The heading that matches, and the rows of the first table under it (header dropped)."""
    heading = re.search(heading_pattern, text, flags=re.M)
    assert heading is not None, f"no heading matching {heading_pattern!r} in the section"
    rows = []
    in_table = False
    for line in text[heading.end() :].splitlines():
        if line.startswith("|"):
            in_table = True
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif in_table:
            break
    assert len(rows) > 2, f"no table under {heading.group(0)!r}"
    return heading, rows[2:]


def _unquote(cell: str) -> str:
    return cell.strip("`")


def _assessor(name: str, version: str) -> AssessorPackage:
    package = AUTOMATED_ASSESSORS.get((name, version))
    assert package is not None, f"the document names {name} v{version}, which is not registered"
    return package


# --- the tests ------------------------------------------------------------------------------


def test_the_summary_counts_what_each_assessor_decides_and_how() -> None:
    published = _published_instruments()
    _, rows = _table_after(_section(), r"^### By assessor$")

    documented = {}
    for row in rows:
        assessor, instrument, *counts = row
        match = re.fullmatch(r"`(?P<name>[^`]+)` v(?P<version>\S+)", assessor)
        assert match, f"cannot read the assessor in {row}"
        documented[(match["name"], match["version"])] = (_unquote(instrument), *counts)

    expected = {}
    for key, package in AUTOMATED_ASSESSORS.items():
        spec = published.get(package.instrument_id)
        if spec is None:
            continue  # its lineage is not published: the workbench measures nothing with it
        decisions = _expected_decisions(package, spec)
        expected[key] = (
            _version_id(spec),
            str(len(decisions)),
            *(
                str(sum(1 for d in decisions.values() if d == kind))
                for kind in (DETERMINISTIC, EXTRACTS, JUDGES, ABSTAINS)
            ),
        )

    assert documented == expected


def test_the_per_criterion_table_matches_the_code() -> None:
    heading, rows = _table_after(
        _section(),
        r"^### Criterion by criterion: `(?P<name>[^`]+)` v(?P<version>\S+) "
        r"over `(?P<instrument>[^`]+)`$",
    )
    package = _assessor(heading["name"], heading["version"])
    spec = _published_instruments()[package.instrument_id]
    assert heading["instrument"] == _version_id(spec), (
        "the table names an instrument version the workbench does not publish"
    )

    documented = {_unquote(criterion): (how, on_v1) for criterion, how, on_v1 in rows}
    decisions = _expected_decisions(package, spec)
    on_v1 = _on_learnpack_v1(spec)
    expected = {
        criterion_id: (decisions[criterion_id], on_v1[criterion_id]) for criterion_id in decisions
    }

    assert list(documented) == list(expected), (
        "the table lists criteria the instrument does not, or in another order"
    )
    assert documented == expected


def test_every_documented_mechanism_is_one_the_section_defines() -> None:
    """A fifth label would be a mechanism nobody explained — the summary has a column per kind."""
    section = _section()
    for label in (DETERMINISTIC, EXTRACTS, JUDGES, ABSTAINS):
        assert f"**{label}**" in section, f"the section never defines '{label}'"
