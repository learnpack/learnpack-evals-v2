"""Anti-corruption layer for LearnPack, the `GeneratingSystem` (05-connect.md).

Translates the external system's shape into our model. In the MVP content is loaded by hand,
so the translation is thin — but the seam lives here, so when LearnPack's API is ingested for
real, nothing outside this file changes.
"""

from typing import Any

from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION

PACKAGE_FORMAT = "LearnpackV1"


def to_register_command(raw: dict[str, Any]) -> RegisterContentVersionCommand:
    """Map a raw LearnPack course payload to `RegisterContentVersion`.

    Only identity and the consumable surface: whatever the platform declares about a
    course travels as package artifacts, never as a side metadata channel (ADR-0017).
    """
    return RegisterContentVersionCommand(
        package_format=PACKAGE_FORMAT,
        external_id=raw["slug"],
        consumable_url=raw["url"],
        version=str(raw.get("version") or DEFAULT_VERSION),
    )
