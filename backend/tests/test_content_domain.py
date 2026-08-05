"""EducationalContent invariants (07-define.md) — pure domain, no DB."""

import pytest

from app.modules.evaluand_registry.domain.content import (
    DEFAULT_VERSION,
    EducationalContent,
    InvalidContent,
)
from app.shared.domain.ids import new_id


def make_content(**overrides) -> EducationalContent:
    kwargs = {
        "id": new_id(),
        "package_format": "LearnpackV1",
        "external_id": "introduction-to-generative-ai",
        "consumable_url": "https://introduction-to-generative-ai.learn-pack.com/",
    }
    return EducationalContent(**(kwargs | overrides))


def test_version_defaults_to_one():
    assert make_content().version == DEFAULT_VERSION


def test_logical_id_is_system_plus_external_id():
    # The logical content groups its versions (ADR-0005).
    content = make_content(version="2")
    assert content.logical_id == ("LearnpackV1", "introduction-to-generative-ai")


@pytest.mark.parametrize(
    "field",
    ["package_format", "external_id", "consumable_url", "version"],
)
def test_required_fields_reject_blanks(field):
    with pytest.raises(InvalidContent):
        make_content(**{field: "   "})


def test_consumable_url_must_be_http():
    with pytest.raises(InvalidContent, match="http"):
        make_content(consumable_url="ftp://example.com/course")


def test_edit_provenance_defaults_to_unknown():
    assert make_content().edit_provenance == "unknown"


def test_invalid_edit_provenance_is_rejected():
    import pytest

    from app.modules.evaluand_registry.domain.content import InvalidContent

    with pytest.raises(InvalidContent, match="edit_provenance"):
        make_content(edit_provenance="ai-ish")


def test_package_defaults_to_empty():
    assert make_content().package.artifacts == ()


def test_package_artifacts_require_kind_and_locator():
    import pytest

    from app.modules.evaluand_registry.domain.package import ContentPackage, InvalidPackage

    with pytest.raises(InvalidPackage, match="locator"):
        ContentPackage.validated([{"kind": "manifest", "locator": "  "}])


def test_package_kind_is_an_open_vocabulary():
    """No enum: a new artifact kind is data, not code (GLOSSARY, ContentPackage)."""
    from app.modules.evaluand_registry.domain.package import ContentPackage

    package = ContentPackage.validated(
        [{"kind": "knowledge-graph", "locator": "https://x/kg.json", "format": "json"}]
    )
    assert package.artifacts[0].kind == "knowledge-graph"
