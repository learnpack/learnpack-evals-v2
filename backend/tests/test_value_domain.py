"""The value domain vocabulary and its checker (ADR-0020). No DB, no I/O.

Two questions kept apart on purpose: is the DECLARATION well formed (`validate_spec`,
asked when a data requirement is minted) and does an extracted VALUE satisfy it
(`check_value`, asked at `ContentProfile.ok()`).
"""

import pytest

from app.shared.domain.value_domain import TYPES, check_value, validate_spec

INVENTORY = {
    "type": "record_list",
    "fields": {
        "lessonId": {"type": "string"},
        "slug": {"type": "string"},
        "position": {"type": "number", "nullable": True},
        "title": {"type": "string", "nullable": True},
    },
}


def lesson(**overrides) -> dict:
    return {"lessonId": "01.0", "slug": "intro", "position": 1, "title": "Intro"} | overrides


# --- validate_spec: is the declaration usable? -----------------------------------------


@pytest.mark.parametrize(
    "domain",
    [
        {"type": "string"},
        {"type": "number", "nullable": True},
        {"type": "boolean"},
        {"type": "string_list"},
        {"type": "record", "fields": {"a": {"type": "string"}}},
        INVENTORY,
        # One level of nesting: the real shape of `lesson_activities`.
        {
            "type": "record_list",
            "fields": {
                "slug": {"type": "string"},
                "activities": {"type": "record", "fields": {"multipleChoice": {"type": "number"}}},
                "codeExercises": {"type": "string_list"},
            },
        },
    ],
)
def test_well_formed_specs_are_accepted(domain):
    assert validate_spec(domain) == []


@pytest.mark.parametrize(
    "domain, expected",
    [
        ("string", "must be a mapping"),
        ({}, "type must be one of"),
        ({"type": "list"}, "type must be one of"),
        ({"type": "record"}, "requires a non-empty `fields`"),
        ({"type": "record", "fields": {}}, "requires a non-empty `fields`"),
        ({"type": "record_list", "fields": []}, "requires a non-empty `fields`"),
        ({"type": "string", "fields": {"a": {"type": "string"}}}, "only applies to"),
        ({"type": "string", "nullable": "yes"}, "nullable must be"),
        ({"type": "string", "feilds": {}}, "unknown keys feilds"),
    ],
)
def test_malformed_specs_are_reported(domain, expected):
    problems = validate_spec(domain)
    assert problems and any(expected in p for p in problems)


def test_a_bad_nested_field_names_its_path():
    domain = {"type": "record_list", "fields": {"activities": {"type": "recrod"}}}
    problems = validate_spec(domain)
    assert any("value_domain.activities" in p for p in problems)


def test_every_type_in_the_vocabulary_can_be_declared():
    """A type named in TYPES that no spec can express would be a trap for an author."""
    for name in TYPES:
        domain = {"type": name}
        if name in ("record", "record_list"):
            domain["fields"] = {"a": {"type": "string"}}
        assert validate_spec(domain) == [], name


# --- check_value: does the extracted value satisfy it? ---------------------------------


@pytest.mark.parametrize(
    "value, domain",
    [
        ("a statement", {"type": "string"}),
        (3, {"type": "number"}),
        (2.5, {"type": "number"}),
        (True, {"type": "boolean"}),
        ([], {"type": "string_list"}),
        (["a", "b"], {"type": "string_list"}),
        ([], INVENTORY),
        ([lesson()], INVENTORY),
        ([lesson(position=None, title=None)], INVENTORY),
        # Undeclared fields are allowed: an adapter may add one without an instrument bump.
        ([lesson(description="a summary")], INVENTORY),
    ],
)
def test_conforming_values_pass(value, domain):
    assert check_value(value, domain) == []


@pytest.mark.parametrize(
    "value, domain, expected",
    [
        (None, {"type": "string"}, "expected string, got null"),
        (7, {"type": "string"}, "expected string, got number"),
        ("7", {"type": "number"}, "expected number, got string"),
        # bool is an int in Python — a flag is not a count.
        (True, {"type": "number"}, "expected number, got boolean"),
        (1, {"type": "boolean"}, "expected boolean, got number"),
        ("abc", {"type": "string_list"}, "expected string_list, got string"),
        ({"a": 1}, INVENTORY, "expected record_list, got record"),
        (lesson(), INVENTORY, "expected record_list, got record"),
    ],
)
def test_non_conforming_values_are_reported(value, domain, expected):
    problems = check_value(value, domain)
    assert problems and any(expected in p for p in problems)


def test_a_null_where_nullable_is_declared_is_fine():
    assert check_value(None, {"type": "string", "nullable": True}) == []


def test_a_missing_required_field_is_a_violation_naming_the_field():
    value = [{"slug": "intro", "position": 1, "title": "Intro"}]
    problems = check_value(value, INVENTORY, "lesson_inventory")
    assert problems == ["lesson_inventory[0].lessonId: required field is missing"]


def test_nullable_is_not_optional_the_field_must_still_be_there():
    """Same discipline as invariant 3: an adapter says "nothing there" with null, not by
    omitting the key. Silence is never evidence (ADR-0009)."""
    assert check_value([lesson(title=None)], INVENTORY) == []

    value = [{"lessonId": "01.0", "slug": "intro", "position": 1}]  # title omitted
    problems = check_value(value, INVENTORY, "lesson_inventory")
    assert problems == ["lesson_inventory[0].title: required field is missing"]


def test_the_path_locates_the_offending_element():
    value = [lesson(), lesson(slug=42)]
    problems = check_value(value, INVENTORY, "lesson_inventory")
    assert problems == ["lesson_inventory[1].slug: expected string, got number"]


def test_every_violation_is_reported_not_just_the_first():
    value = [{"lessonId": 1, "slug": 2, "position": "x", "title": "ok"}]
    assert len(check_value(value, INVENTORY, "lesson_inventory")) == 3


def test_a_bad_element_inside_a_string_list_names_its_index():
    problems = check_value(["a", 2], {"type": "string_list"}, "prerequisites")
    assert problems == ["prerequisites[1]: expected string, got number"]


def test_an_unknown_type_is_reported_rather_than_silently_accepted():
    """A silent pass is exactly the failure mode this vocabulary exists to remove."""
    problems = check_value("anything", {"type": "made_up"})
    assert problems and "unknown value domain type" in problems[0]
