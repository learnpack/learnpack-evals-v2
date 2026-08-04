"""MetadataSchema validation (ADR-0001) — pure domain, no DB.

The schema is reference data, so these tests exercise it generically: the domain must not
know that 'learningObjectives' exists.
"""

import pytest

from app.modules.evaluand_registry.domain.metadata import (
    ContentMetadata,
    InvalidMetadata,
    MetadataSchema,
    ValueType,
)

SPEC = {
    "learningObjectives": {"valueType": "string_list", "required": True},
    "targetAudience": {"valueType": "string", "required": True},
    "prerequisites": {"valueType": "string_list", "required": False},
}

VALID = {
    "learningObjectives": ["Explain prompting", "Compare models"],
    "targetAudience": "Junior developers",
    "prerequisites": ["Basic Python"],
}


@pytest.fixture
def schema() -> MetadataSchema:
    return MetadataSchema.from_spec("LearnpackV1", SPEC)


def test_valid_metadata_has_no_errors(schema):
    assert schema.validate(VALID) == []


def test_optional_key_may_be_absent(schema):
    values = {k: v for k, v in VALID.items() if k != "prerequisites"}
    assert schema.validate(values) == []


def test_missing_required_key_is_reported(schema):
    values = {k: v for k, v in VALID.items() if k != "targetAudience"}
    errors = schema.validate(values)
    assert len(errors) == 1
    assert "targetAudience" in errors[0]


def test_unknown_key_is_rejected(schema):
    # The lessonPlan churn (ADR-0001) is exactly what this prevents.
    errors = schema.validate(VALID | {"lessonPlan": "..."})
    assert any("lessonPlan" in e for e in errors)


def test_string_key_rejects_a_list(schema):
    errors = schema.validate(VALID | {"targetAudience": ["a", "b"]})
    assert any("targetAudience" in e and "string" in e for e in errors)


def test_string_list_key_rejects_a_bare_string(schema):
    errors = schema.validate(VALID | {"learningObjectives": "just one"})
    assert any("learningObjectives" in e for e in errors)


def test_string_list_key_rejects_non_string_items(schema):
    errors = schema.validate(VALID | {"learningObjectives": ["ok", 42]})
    assert any("learningObjectives" in e for e in errors)


def test_all_violations_are_reported_together(schema):
    errors = schema.validate({"targetAudience": 1, "nope": "x"})
    # missing learningObjectives + wrong type + unknown key
    assert len(errors) == 3


def test_entries_take_their_value_type_from_the_schema(schema):
    entries = {e.key: e for e in schema.entries(VALID)}
    assert entries["targetAudience"].value_type is ValueType.STRING
    assert entries["learningObjectives"].value_type is ValueType.STRING_LIST


def test_validated_metadata_raises_with_every_error(schema):
    with pytest.raises(InvalidMetadata) as exc:
        ContentMetadata.validated({"lessonPlan": "x"}, schema)
    assert len(exc.value.errors) == 3


def test_trusted_metadata_skips_validation():
    # Persisted values must stay readable even if the schema moved on.
    assert ContentMetadata.trusted({"whatever": 1}).values == {"whatever": 1}
