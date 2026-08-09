"""Anti-corruption layer for LearnPack, the `GeneratingSystem`.

Its remaining job is brief derivation (ADR-0022): translating the syllabus LearnPack ships
inside the package into the commission's identity. Registering *from* LearnPack is the
discovery ACL's job (`package_discovery`, ADR-0027) — the slice-1 payload translation that
used to live here retired with it.
"""

import hashlib
import json
from typing import Any

from app.modules.evaluand_registry.application.ports import DerivedBrief

PACKAGE_FORMAT = "LearnpackV1"

SYLLABUS_LOCATOR_SUFFIX = ".learn/initialSyllabus.json"


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
