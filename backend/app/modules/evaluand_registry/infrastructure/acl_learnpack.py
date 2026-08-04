"""Anti-corruption layer for LearnPack, the `GeneratingSystem` (05-connect.md).

Translates the external system's shape into our model. In the MVP content is loaded by hand,
so the translation is thin — but the seam lives here, so when LearnPack's API is ingested for
real, nothing outside this file changes.
"""

from typing import Any

from app.modules.evaluand_registry.application.register_content import RegisterContentCommand
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION

PACKAGE_FORMAT = "LearnpackV1"

# LearnPack's field names on the left, ours (the seeded schema's keys) on the right.
_METADATA_FIELD_MAP = {
    "objectives": "learningObjectives",
    "learningObjectives": "learningObjectives",
    "audience": "targetAudience",
    "targetAudience": "targetAudience",
    "prerequisites": "prerequisites",
}


def to_register_command(raw: dict[str, Any]) -> RegisterContentCommand:
    """Map a raw LearnPack course payload to `RegisterContent`."""
    metadata = {
        _METADATA_FIELD_MAP[key]: value
        for key, value in (raw.get("metadata") or {}).items()
        if key in _METADATA_FIELD_MAP
    }
    return RegisterContentCommand(
        package_format=PACKAGE_FORMAT,
        external_id=raw["slug"],
        consumable_url=raw["url"],
        version=str(raw.get("version") or DEFAULT_VERSION),
        metadata=metadata,
    )
