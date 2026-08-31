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
    ["package_format", "external_id", "version"],
)
def test_required_fields_reject_blanks(field):
    with pytest.raises(InvalidContent):
        make_content(**{field: "   "})


def test_consumable_url_must_be_http():
    with pytest.raises(InvalidContent, match="http"):
        make_content(consumable_url="ftp://example.com/course")


def test_a_content_may_declare_no_consumable_url():
    """ADR-0028: the URL declares a deployed instance, and a package nobody hosts has none.
    The version is still a complete evaluand — what a null closes is the human path."""
    assert make_content(consumable_url=None).consumable_url is None


def test_a_declared_consumable_url_may_not_be_blank():
    """A blank is never coerced into a null: a caller that means "none" passes None."""
    with pytest.raises(InvalidContent, match="http"):
        make_content(consumable_url="   ")


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


# ------------------------------------------------------------------ the declared title


def test_a_course_has_no_title_until_its_package_declares_one():
    """Null is the honest value (ADR-0059 §3): nothing derives a name from the slug."""
    assert make_content().title is None


def test_a_blank_declared_title_is_no_title():
    assert make_content(title="   ").title is None


def test_recording_a_title_fills_a_void():
    content = make_content()
    content.record_discovered_title("  Introduction to Generative AI  ")
    assert content.title == "Introduction to Generative AI"


def test_a_recorded_title_is_never_replaced():
    """One-way, like the generator link: the fact was always true and merely arrived late,
    so a second write would be a rename — the act ADR-0059 §1 refuses."""
    from app.modules.evaluand_registry.domain.content import TitleAlreadyRecorded

    content = make_content(title="Introduction to Generative AI")
    with pytest.raises(TitleAlreadyRecorded):
        content.record_discovered_title("Something Else")
    assert content.title == "Introduction to Generative AI"


def test_recording_a_blank_title_is_refused():
    with pytest.raises(InvalidContent, match="blank"):
        make_content().record_discovered_title("   ")
