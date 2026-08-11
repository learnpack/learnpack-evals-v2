"""Anti-corruption layer for LearnpackV2, the generator's run-output format.

Its job is brief derivation (ADR-0022). Where LearnpackV1 has to *read a commission out of*
a derived syllabus, LearnpackV2 carries the request the run was started from:
`files/course_request.json` is a `{"content": …}` envelope around whatever the creator
wrote, and `content` is that text, unparsed.

The envelope is structure; the commission is not. What the creator writes has no declared
shape — headings, prose, bullet points, as much or as little detail as they chose — so
nothing is read out of `content` and it is preserved verbatim.

`brief_hash` covers the **content**, never the envelope: the commission's identity is the
instruction, so re-wrapping the same request cannot mint a second brief.

That is also why this format records `promptRecorded: True`: the study report's caveats list
briefs whose original prompt was never persisted (V1's case), and for V2 it was.
"""

import hashlib
import json
from typing import Any

from app.modules.evaluand_registry.application.ports import DerivedBrief

PACKAGE_FORMAT = "LearnpackV2"

COURSE_REQUEST_LOCATOR_SUFFIX = "files/course_request.json"


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_brief(request_bytes: bytes) -> DerivedBrief | None:
    """Translate `files/course_request.json` into the commission's identity (ADR-0022).

    Returns None when the envelope carries no request to speak of — unreadable, the wrong
    shape, or a `content` that is blank. `fields` stays demand-driven: only what the study
    report consumes.
    """
    request: Any = json.loads(request_bytes.decode("utf-8"))
    if not isinstance(request, dict):
        return None
    content = request.get("content")
    if not isinstance(content, str) or not content.strip():
        return None

    return DerivedBrief(
        brief=content,
        fields={"origin": "generation_seed", "promptRecorded": True},
        brief_hash=_sha256(content),
    )
