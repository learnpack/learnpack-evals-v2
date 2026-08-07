"""Anti-corruption layer for LearnPack, the `GeneratingSystem` (05-connect.md).

Translates the external system's shape into our model. In the MVP content is loaded by hand,
so the translation is thin — but the seam lives here, so when LearnPack's API is ingested for
real, nothing outside this file changes.
"""

import hashlib
import json
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.application.ports import DerivedBrief
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION

PACKAGE_FORMAT = "LearnpackV1"

SYLLABUS_LOCATOR_SUFFIX = ".learn/initialSyllabus.json"


def to_register_command(
    raw: dict[str, Any], generator_version_id: UUID | None
) -> RegisterContentVersionCommand:
    """Map a raw LearnPack course payload to `RegisterContentVersion`.

    Only identity and the consumable surface: whatever the platform declares about a
    course travels as package artifacts, never as a side metadata channel (ADR-0017).

    LearnPack's shape carries no generator, so the declaration (ADR-0024) cannot come from
    the payload — the caller supplies it, and `None` declares `unknown`.
    """
    return RegisterContentVersionCommand(
        package_format=PACKAGE_FORMAT,
        external_id=raw["slug"],
        consumable_url=raw["url"],
        version=str(raw.get("version") or DEFAULT_VERSION),
        generator_version_id=generator_version_id,
    )


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_brief(syllabus_bytes: bytes) -> DerivedBrief | None:
    """Translate `.learn/initialSyllabus.json` into the brief's identity (ADR-0022).

    `courseInfo.description` is the operative instruction during lesson generation;
    `courseInfo.contentIndex` identifies the attached material (hashed, not duplicated).
    Returns None when the syllabus carries no usable description.
    """
    data = json.loads(syllabus_bytes.decode("utf-8"))
    course_info = data.get("courseInfo") if isinstance(data, dict) else None
    if not isinstance(course_info, dict):
        return None
    description = course_info.get("description")
    if not isinstance(description, str) or not description.strip():
        return None

    # Canonical JSON so the hash survives key reordering between exports.
    materials_hash = _sha256(
        json.dumps(course_info.get("contentIndex"), sort_keys=True, separators=(",", ":"))
    )
    fields: dict[str, Any] = {
        "origin": "ai_derived_syllabus",
        "promptRecorded": False,  # the original prompt is not persisted by the pipeline
        "materialsHash": materials_hash,
    }
    if course_info.get("materialsSource"):
        fields["materialsSource"] = course_info["materialsSource"]

    return DerivedBrief(
        brief=description,
        fields=fields,
        brief_hash=_sha256(f"{description}\n{materials_hash}"),
    )
