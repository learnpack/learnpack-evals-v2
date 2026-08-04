"""EducationalContent invariants (07-define.md) — pure domain, no DB."""

import pytest

from app.modules.evaluand_registry.domain.content import (
    DEFAULT_VERSION,
    EducationalContent,
    InvalidContent,
)
from app.modules.evaluand_registry.domain.metadata import (
    ContentMetadata,
    InvalidMetadata,
    MetadataSchema,
)
from app.shared.domain.ids import new_id

SCHEMA = MetadataSchema.from_spec(
    "LearnpackV1", {"targetAudience": {"valueType": "string", "required": True}}
)


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


def test_update_metadata_revalidates_against_the_schema():
    content = make_content()
    content.update_metadata({"targetAudience": "Junior developers"}, SCHEMA)
    assert content.metadata.values["targetAudience"] == "Junior developers"

    with pytest.raises(InvalidMetadata):
        content.update_metadata({"targetAudience": 42}, SCHEMA)
    # The aggregate is unchanged after a rejected update.
    assert content.metadata.values["targetAudience"] == "Junior developers"


def test_metadata_defaults_to_empty():
    assert make_content().metadata == ContentMetadata(values={})
