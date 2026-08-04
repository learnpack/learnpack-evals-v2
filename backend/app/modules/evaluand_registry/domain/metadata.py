"""Open, typed content metadata (ADR-0001) — pure Python.

The domain never references a concrete key (`learningObjectives`, `targetAudience`, ...).
It only knows that a `MetadataSchema` — reference data bound to a `GeneratingSystem` —
declares which keys are allowed, which are required, and of what type. Adding a new content
type is therefore config, not code.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ValueType(StrEnum):
    STRING = "string"
    STRING_LIST = "string_list"


class InvalidMetadata(Exception):
    """Metadata does not satisfy its schema. Carries every error, not just the first."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class MetadataEntry:
    """A single `{key, value, valueType}` — the unit other layers render."""

    key: str
    value: Any
    value_type: ValueType


@dataclass(frozen=True)
class KeySpec:
    value_type: ValueType
    required: bool = False


@dataclass(frozen=True)
class MetadataSchema:
    """Declares allowed/required keys and their types for a GeneratingSystem."""

    package_format: str
    keys: dict[str, KeySpec]

    @classmethod
    def from_spec(cls, package_format: str, spec: dict[str, Any]) -> "MetadataSchema":
        """Build from the JSONB stored in `metadata_schemas.spec` (reference data)."""
        keys = {}
        for key, raw in spec.items():
            keys[key] = KeySpec(
                value_type=ValueType(raw["valueType"]),
                required=bool(raw.get("required", False)),
            )
        return cls(package_format=package_format, keys=keys)

    def validate(self, values: dict[str, Any]) -> list[str]:
        """Return every violation. Empty list means valid."""
        errors: list[str] = []

        for key in values:
            if key not in self.keys:
                errors.append(f"unknown metadata key '{key}' for {self.package_format}")

        for key, spec in self.keys.items():
            if key not in values or values[key] is None:
                if spec.required:
                    errors.append(f"missing required metadata key '{key}'")
                continue
            errors.extend(self._type_errors(key, values[key], spec.value_type))

        return errors

    @staticmethod
    def _type_errors(key: str, value: Any, value_type: ValueType) -> list[str]:
        if value_type is ValueType.STRING:
            if not isinstance(value, str):
                return [f"metadata key '{key}' must be a string"]
        elif value_type is ValueType.STRING_LIST:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return [f"metadata key '{key}' must be a list of strings"]
        return []

    def entries(self, values: dict[str, Any]) -> list[MetadataEntry]:
        """Pair stored values with their declared type.

        Values are stored as a plain map; the `valueType` lives here, in the schema, so it
        is never duplicated per row (08-code.md §3).
        """
        return [
            MetadataEntry(key=key, value=values[key], value_type=spec.value_type)
            for key, spec in self.keys.items()
            if key in values and values[key] is not None
        ]


@dataclass(frozen=True)
class ContentMetadata:
    """An open collection of values, valid against a schema at construction time."""

    values: dict[str, Any]

    @classmethod
    def validated(cls, values: dict[str, Any], schema: MetadataSchema) -> "ContentMetadata":
        errors = schema.validate(values)
        if errors:
            raise InvalidMetadata(errors)
        return cls(values=dict(values))

    @classmethod
    def trusted(cls, values: dict[str, Any]) -> "ContentMetadata":
        """Rehydrate already-persisted values without revalidating.

        A stored schema may have evolved after the fact; reading must not fail because of it.
        """
        return cls(values=dict(values))
