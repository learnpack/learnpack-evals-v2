"""Domain invariants of GeneratorVersion, GenerationBrief and GeneratorArtifact — no DB."""

import pytest

from app.modules.evaluand_registry.domain.brief import GenerationBrief, InvalidBrief
from app.modules.evaluand_registry.domain.generator import (
    GeneratorArtifact,
    GeneratorVersion,
    InvalidGeneratorArtifact,
    InvalidGeneratorVersion,
)
from app.shared.domain.ids import new_id


def test_generator_version_holds_its_declared_identity():
    generator = GeneratorVersion(id=new_id(), name="learnpack-generator", version="2.4.0")
    assert generator.metadata == {}


@pytest.mark.parametrize("attr", ["name", "version"])
def test_generator_version_requires_its_identity_fields(attr):
    kwargs = {"id": new_id(), "name": "gen", "version": "1.0"} | {attr: "   "}
    with pytest.raises(InvalidGeneratorVersion, match=attr):
        GeneratorVersion(**kwargs)


def test_generator_version_is_immutable():
    generator = GeneratorVersion(id=new_id(), name="gen", version="1.0")
    with pytest.raises(AttributeError):
        generator.version = "2.0"  # type: ignore[misc]


def test_brief_requires_text():
    with pytest.raises(InvalidBrief, match="brief"):
        GenerationBrief(id=new_id(), brief="  ")


def test_brief_defaults_to_no_typed_fields():
    """Lean on purpose: typed fields appear only when task variables consume them."""
    brief = GenerationBrief(id=new_id(), brief="an intro course on loops")
    assert brief.fields == {}


@pytest.mark.parametrize("attr", ["kind", "locator"])
def test_generator_artifact_requires_kind_and_locator(attr):
    kwargs = {
        "id": new_id(),
        "generator_version_id": new_id(),
        "kind": "prompt-template",
        "locator": "https://example.com/t",
    } | {attr: ""}
    with pytest.raises(InvalidGeneratorArtifact, match=attr):
        GeneratorArtifact(**kwargs)
