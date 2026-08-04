"""The LearnPack ACL (05-connect.md) — translates the external model into ours.

Pure mapping, no DB. This is the seam that absorbs LearnPack's field names so they never
leak into the domain.
"""

from app.modules.evaluand_registry.infrastructure.acl_learnpack import to_register_command

RAW = {
    "slug": "introduction-to-generative-ai",
    "url": "https://introduction-to-generative-ai.learn-pack.com/",
    "metadata": {
        "objectives": ["Explain prompting"],
        "audience": "Junior developers",
    },
}


def test_maps_external_fields_to_our_command():
    command = to_register_command(RAW)

    assert command.generating_system == "LearnpackV1"
    assert command.external_id == "introduction-to-generative-ai"
    assert command.consumable_url == RAW["url"]
    assert command.version == "1"
    # LearnPack's names become the schema's keys.
    assert command.metadata == {
        "learningObjectives": ["Explain prompting"],
        "targetAudience": "Junior developers",
    }


def test_accepts_our_own_key_names_too():
    command = to_register_command(
        RAW | {"metadata": {"learningObjectives": ["x"], "prerequisites": ["Python"]}}
    )
    assert command.metadata == {"learningObjectives": ["x"], "prerequisites": ["Python"]}


def test_unknown_external_fields_are_dropped():
    # Unmapped fields are the ACL's problem, not the domain's — they never reach validation.
    command = to_register_command(RAW | {"metadata": {"lessonPlan": "...", "audience": "Devs"}})
    assert command.metadata == {"targetAudience": "Devs"}


def test_version_is_carried_through():
    assert to_register_command(RAW | {"version": 2}).version == "2"


def test_missing_metadata_yields_an_empty_map():
    assert to_register_command({"slug": "a", "url": "https://a.com"}).metadata == {}
