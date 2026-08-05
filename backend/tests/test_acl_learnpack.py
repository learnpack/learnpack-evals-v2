"""The LearnPack ACL (05-connect.md) — translates the external model into ours.

Pure mapping, no DB. This is the seam that absorbs LearnPack's field names so they never
leak into the domain. Since ADR-0017 it maps identity and the consumable surface only:
whatever the platform declares about a course travels as package artifacts, so any
`metadata` in the external payload is deliberately ignored.
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

    assert command.package_format == "LearnpackV1"
    assert command.external_id == "introduction-to-generative-ai"
    assert command.consumable_url == RAW["url"]
    assert command.version == "1"


def test_external_metadata_is_ignored_not_registered():
    # The command has no metadata at all (ADR-0017): a payload carrying it changes nothing.
    command = to_register_command(RAW)
    assert not hasattr(command, "metadata")


def test_version_is_carried_through():
    assert to_register_command(RAW | {"version": 2}).version == "2"
