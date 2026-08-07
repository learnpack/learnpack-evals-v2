"""Value domains — the declared shape of a `data_requirement`'s value (ADR-0020).

Shared kernel between the two sides of the ADR-0014 contract: Evaluation Design mints the
id and declares the shape; Content Profiling checks that what an adapter actually
extracted has it. One grammar, one checker, so the two cannot drift.

Two questions, deliberately separate:

- `validate_spec` — is the declaration itself well formed? Asked when a data requirement is
  minted (authoring time). Strict about unknown keys: a typo like `feilds` would otherwise
  silently disable the check it was meant to install.
- `check_value` — does an extracted value satisfy it? Asked at `ContentProfile.ok()`, the
  chokepoint every adapter passes through.

Both return a list of problems (empty = fine) rather than raising, so a caller can report
everything at once — the accumulation style of `InstrumentVersion.publish()`.

The vocabulary is demand-driven (13-code §7.4): exactly what the minted ids consume today.
`record`/`record_list` declare the fields that MUST be there and their types; a field the
declaration does not name is not a violation, so an adapter that starts emitting an extra
field does not force an instrument version bump — the two version axes stay independent.
`enum`, `levels` and `citation` are named vocabulary, not built: no id consumes them yet.

`nullable: true` means the field must be PRESENT and may be null — it is not optionality.
Same discipline as invariant 3 one level up (declared capability + missing data ⇒ an
explicit `absent` entry, never a missing row): an adapter says "I looked and there was
nothing" by emitting null, not by omitting the key. Silence is never evidence.
"""

from collections.abc import Mapping
from typing import Any

TYPES = ("string", "number", "boolean", "string_list", "record", "record_list")
FIELDED_TYPES = ("record", "record_list")
SPEC_KEYS = ("type", "nullable", "fields")


def validate_spec(domain: Any, path: str = "") -> list[str]:
    """Problems with the declaration itself. Empty list = a usable value domain."""
    where = path or "value_domain"
    if not isinstance(domain, Mapping):
        return [f"{where}: must be a mapping, got {_kind(domain)}"]

    problems: list[str] = []
    unknown_keys = sorted(set(domain) - set(SPEC_KEYS))
    if unknown_keys:
        problems.append(
            f"{where}: unknown keys {', '.join(unknown_keys)} (allowed: {', '.join(SPEC_KEYS)})"
        )
    if "nullable" in domain and not isinstance(domain["nullable"], bool):
        problems.append(f"{where}: nullable must be true or false")

    declared = domain.get("type")
    if declared not in TYPES:
        problems.append(f"{where}: type must be one of {', '.join(TYPES)}, got {declared!r}")
        return problems

    fields = domain.get("fields")
    if declared in FIELDED_TYPES:
        if not isinstance(fields, Mapping) or not fields:
            problems.append(f"{where}: {declared} requires a non-empty `fields` mapping")
        else:
            for name, sub in fields.items():
                problems.extend(validate_spec(sub, _join(where, str(name))))
    elif fields is not None:
        problems.append(f"{where}: `fields` only applies to {', '.join(FIELDED_TYPES)}")

    return problems


def check_value(value: Any, domain: Mapping[str, Any], path: str = "") -> list[str]:
    """Problems with an extracted value against its declared domain.

    Assumes `domain` passed `validate_spec` (enforced when the requirement is minted); an
    unrecognised type is still reported rather than silently accepted.
    """
    where = path or "value"
    declared = domain.get("type")

    if value is None:
        if domain.get("nullable") is True:
            return []
        return [f"{where}: expected {declared}, got null"]

    if declared == "string":
        return [] if isinstance(value, str) else [_mismatch(where, "string", value)]
    if declared == "number":
        # bool is a subclass of int in Python — a flag is not a count.
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        return [] if ok else [_mismatch(where, "number", value)]
    if declared == "boolean":
        return [] if isinstance(value, bool) else [_mismatch(where, "boolean", value)]
    if declared == "string_list":
        if not isinstance(value, list):
            return [_mismatch(where, "string_list", value)]
        return [
            _mismatch(_index(where, i), "string", item)
            for i, item in enumerate(value)
            if not isinstance(item, str)
        ]
    if declared == "record":
        return _check_record(value, domain, where)
    if declared == "record_list":
        if not isinstance(value, list):
            return [_mismatch(where, "record_list", value)]
        problems: list[str] = []
        for i, item in enumerate(value):
            problems.extend(_check_record(item, domain, _index(where, i)))
        return problems

    return [f"{where}: unknown value domain type {declared!r}"]


def _check_record(value: Any, domain: Mapping[str, Any], where: str) -> list[str]:
    """A record satisfies its domain when every DECLARED field is present and conforms.

    Undeclared fields are allowed on purpose (see the module docstring).
    """
    if not isinstance(value, Mapping):
        return [_mismatch(where, "record", value)]
    problems: list[str] = []
    fields: Mapping[str, Any] = domain.get("fields") or {}
    for name, sub in fields.items():
        location = _join(where, name)
        if name not in value:
            problems.append(f"{location}: required field is missing")
            continue
        problems.extend(check_value(value[name], sub, location))
    return problems


def _mismatch(where: str, expected: str, value: Any) -> str:
    return f"{where}: expected {expected}, got {_kind(value)}"


def _kind(value: Any) -> str:
    """The reader of these messages is debugging an adapter — name what they'd recognise."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, Mapping):
        return "record"
    return type(value).__name__


def _join(path: str, name: str) -> str:
    return f"{path}.{name}" if path else name


def _index(path: str, index: int) -> str:
    return f"{path}[{index}]"
