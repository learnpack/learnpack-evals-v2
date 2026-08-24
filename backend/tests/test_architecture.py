"""The hard rules of ARCHITECTURE.md, made executable.

These are not style checks: breaking one of them breaks the Dependency Rule or module
isolation, which is what keeps this codebase able to grow into the target model. They run on
every `pytest`, need no database, and are cheap.
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

FRAMEWORKS = {"fastapi", "sqlalchemy", "pydantic", "pydantic_settings", "httpx", "jwt", "alembic"}

# The composition root wires concrete adapters into ports — that is its whole job, so it is
# the one place allowed to name them (ARCHITECTURE.md §3).
COMPOSITION_ROOT = ("platform/", "main.py", "cli.py")

# Layers of a module that are private to it. `public.py` is the exception: it *is* the
# published surface.
PRIVATE_LAYERS = ("domain", "infrastructure")


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: pathlib.Path) -> list[tuple[str, int]]:
    """Every imported module path in `path`, with its line number."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.module, node.lineno))
    return found


def _relative(path: pathlib.Path) -> str:
    return path.relative_to(APP).as_posix()


def _owning_module(path: pathlib.Path) -> str | None:
    """The module a file belongs to, or None if it is not inside `app/modules/`."""
    parts = path.relative_to(APP).parts
    return parts[1] if len(parts) > 2 and parts[0] == "modules" else None


def test_domain_is_pure_python():
    """Domain has zero framework imports — no FastAPI, SQLAlchemy, pydantic, I/O."""
    violations = []
    for path in _python_files(APP):
        parts = path.relative_to(APP).parts
        if "domain" not in parts:
            continue
        for module, line in _imports(path):
            if module.split(".")[0] in FRAMEWORKS:
                violations.append(f"{_relative(path)}:{line} imports {module}")

    assert not violations, "Domain must be pure Python (ARCHITECTURE.md §1):\n" + "\n".join(
        violations
    )


def test_modules_do_not_reach_into_each_others_internals():
    """A module may import another only through its `public.py` (ARCHITECTURE.md §3).

    Importing `modules/<other>/domain` or `modules/<other>/infrastructure` couples this
    module to the other's internals — or to its concrete adapter, which defeats the port.
    """
    violations = []
    for path in _python_files(APP):
        relative = _relative(path)
        if relative.startswith(COMPOSITION_ROOT):
            continue
        owner = _owning_module(path)

        for module, line in _imports(path):
            parts = module.split(".")
            if len(parts) < 4 or parts[:2] != ["app", "modules"]:
                continue
            target, layer = parts[2], parts[3]
            if target == owner or layer not in PRIVATE_LAYERS:
                continue
            violations.append(
                f"{relative}:{line} imports {module} (use app.modules.{target}.public instead)"
            )

    assert not violations, "Module isolation broken (ARCHITECTURE.md §3):\n" + "\n".join(violations)


def test_application_layer_does_not_depend_on_other_modules():
    """Use cases stay module-local; composition happens in infrastructure/composition root."""
    violations = []
    for path in _python_files(APP):
        owner = _owning_module(path)
        if owner is None or "application" not in path.relative_to(APP).parts:
            continue
        for module, line in _imports(path):
            parts = module.split(".")
            if len(parts) >= 3 and parts[:2] == ["app", "modules"] and parts[2] != owner:
                violations.append(f"{_relative(path)}:{line} imports {module}")

    assert not violations, "An application layer must not depend on another module:\n" + "\n".join(
        violations
    )


def test_every_consumed_module_publishes_a_public_surface():
    """A module needs `public.py` if and only if another module imports it.

    Derived rather than hardcoded, so it stays true as modules are added — and so a leaf
    module nobody consumes (reporting) is not forced into an empty file of ceremony.
    """
    consumed: dict[str, str] = {}
    for path in _python_files(APP):
        # The composition root importing a router is wiring, not consuming a contract.
        if _relative(path).startswith(COMPOSITION_ROOT):
            continue
        owner = _owning_module(path)
        for module, line in _imports(path):
            parts = module.split(".")
            if len(parts) < 3 or parts[:2] != ["app", "modules"] or parts[2] == owner:
                continue
            consumed.setdefault(parts[2], f"{_relative(path)}:{line}")

    missing = [
        f"module '{name}' is imported by {where} but has no public.py"
        for name, where in sorted(consumed.items())
        if not (APP / "modules" / name / "public.py").exists()
    ]
    assert not missing, "Consumed modules must publish a contract (ARCHITECTURE.md §3):\n" + (
        "\n".join(missing)
    )


def _exception_classes(paths: list[pathlib.Path]) -> dict[str, list[str]]:
    """`{class name: [files]}` for every exception defined across one module's files.

    Exception-ness is resolved **within the module**, iterating until nothing new is found,
    so a local hierarchy counts too: `LlmError(Exception)` makes `LlmConfigurationError(LlmError)`
    one. A class whose base comes from outside the module is not chased — the rule is about a
    name meaning one thing here, and a missed class is a gap, never a false accusation.
    """
    defined: dict[str, list[tuple[str, list[str]]]] = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
                defined.setdefault(node.name, []).append((_relative(path), bases))

    exceptions = {"Exception"}
    while True:
        found = {
            name
            for name, definitions in defined.items()
            if name not in exceptions
            and any(set(bases) & exceptions for _file, bases in definitions)
        }
        if not found:
            break
        exceptions |= found

    return {
        name: [file for file, _bases in definitions]
        for name, definitions in defined.items()
        if name in exceptions
    }


def test_an_exception_name_means_one_thing_within_a_module():
    """Two exceptions with one name inside a module is a defect that hides (ARCHITECTURE.md §3).

    `except` matches the class, not the name, so the second definition is caught by nobody:
    the refusal escapes its handler and leaves as a 500 where the code says 404. Neither mypy
    nor ruff can see it — both classes are valid, and the `except` clause is type-correct — and
    every line reads right. This is the check that would have caught it.

    Across modules is a different question and deliberately allowed: Evaluand Registry and
    Content Profiling both have a `ContentNotFound` meaning different things, and the caller
    that needs both aliases one.
    """
    violations = []
    for module in sorted(p.name for p in (APP / "modules").iterdir() if p.is_dir()):
        paths = _python_files(APP / "modules" / module)
        for name, files in sorted(_exception_classes(paths).items()):
            if len(files) > 1:
                violations.append(f"{module}: '{name}' is defined in {', '.join(sorted(files))}")

    assert not violations, (
        "An exception name must mean one thing within a module (ARCHITECTURE.md §3) — move the "
        "shared one to the module's application/errors.py:\n" + "\n".join(violations)
    )
