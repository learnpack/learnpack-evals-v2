"""Domain invariants of Generator, GeneratorVersion and GenerationBrief — no DB."""

import pytest

from app.modules.evaluand_registry.domain.brief import GenerationBrief, InvalidBrief
from app.modules.evaluand_registry.domain.generator import (
    NEAR_MISS_DISTANCE,
    Generator,
    GeneratorVersion,
    InvalidGenerator,
    InvalidGeneratorVersion,
    canonical_name,
    edit_distance,
    nearest_name,
    normalized_name,
)
from app.shared.domain.ids import new_id


def test_generator_version_holds_its_declared_identity():
    version = GeneratorVersion(id=new_id(), generator_id=new_id(), version="2.4.0")
    assert version.metadata == {}


def test_generator_version_requires_a_version():
    with pytest.raises(InvalidGeneratorVersion, match="version"):
        GeneratorVersion(id=new_id(), generator_id=new_id(), version="   ")


def test_generator_requires_a_name():
    with pytest.raises(InvalidGenerator, match="name"):
        Generator(id=new_id(), name="   ")


def test_generator_version_is_immutable():
    version = GeneratorVersion(id=new_id(), generator_id=new_id(), version="1.0")
    with pytest.raises(AttributeError):
        version.version = "2.0"  # type: ignore[misc]


# --- The lineage's naming rules (ADR-0031) ------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  LearnPack-Gen  ", "learnpack-gen"),
        ("learnpack   gen", "learnpack gen"),
        ("LEARNPACK-GEN", "learnpack-gen"),
    ],
)
def test_the_key_folds_case_and_whitespace_and_nothing_else(raw, expected):
    assert normalized_name(raw) == expected


def test_the_canonical_form_folds_separators_too():
    forms = {"learnpack_gen", "learnpack.gen", "LearnPack Gen", "learnpack-gen"}
    assert {canonical_name(form) for form in forms} == {"learnpack-gen"}
    # But the key does not: only the guard may treat these as the same lineage.
    assert len({normalized_name(form) for form in forms}) > 1


def test_edit_distance_gives_up_once_it_passes_the_cap():
    # The exact distance is 5; the guard only ever asks "is this within 2?".
    assert edit_distance("alpha", "omegas", cap=NEAR_MISS_DISTANCE) == NEAR_MISS_DISTANCE + 1
    assert edit_distance("gen-alpha", "gen-alpah", cap=NEAR_MISS_DISTANCE) == 2
    assert edit_distance("gen", "gen", cap=NEAR_MISS_DISTANCE) == 0


def test_a_near_miss_names_the_registered_spelling_not_the_folded_one():
    assert nearest_name("learnpack-genertor", ["LearnPack-Generator"]) == "LearnPack-Generator"


def test_an_unrelated_name_is_not_a_near_miss():
    assert nearest_name("course-builder", ["learnpack-generator"]) is None


def test_short_names_are_held_to_a_tighter_threshold():
    # Two edits apart, but at this length that is most of the name — without the floor the
    # guard would question every short name against every other.
    assert nearest_name("gpt", ["abc"]) is None
    assert nearest_name("gpt", ["gpt2"]) == "gpt2"


def test_brief_requires_text():
    with pytest.raises(InvalidBrief, match="brief"):
        GenerationBrief(id=new_id(), brief="  ")


def test_brief_defaults_to_no_typed_fields():
    """Lean on purpose: typed fields appear only when task variables consume them."""
    brief = GenerationBrief(id=new_id(), brief="an intro course on loops")
    assert brief.fields == {}
