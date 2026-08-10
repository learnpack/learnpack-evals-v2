"""Anti-corruption layer for LearnpackV2, the generator's run-output format.

Its job is brief derivation (ADR-0022). Where LearnpackV1 has to *read a commission out of*
a derived syllabus, LearnpackV2 embeds the generation seed itself: `files/course_brief.md`
is the instruction the run was started from, byte for byte. So the translation is the
identity — the commission is the seed's own text, unparsed.

That is also why this format records `promptRecorded: True`: the study report's caveats
list briefs whose original prompt was never persisted (V1's case), and for V2 it was.
"""

import hashlib

from app.modules.evaluand_registry.application.ports import DerivedBrief

PACKAGE_FORMAT = "LearnpackV2"

COURSE_BRIEF_LOCATOR_SUFFIX = "files/course_brief.md"

# Tab, newline and carriage return are the only C0 controls a text document carries.
_TEXTUAL_CONTROLS = "\t\n\r"


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def derive_brief(seed_bytes: bytes) -> DerivedBrief | None:
    """Translate `files/course_brief.md` into the commission's identity (ADR-0022).

    The seed has **no declared shape** — a run is started from whatever the creator wrote,
    with whatever headings and detail they chose — so nothing is parsed out of it and the
    text is preserved verbatim. `fields` stays demand-driven: only what the study report
    consumes.

    Returns None when the payload is not a text document at all. A format whose commission
    is structured gets that check for free from its parser; free text needs it stated, and
    it is a real distinction rather than a formality — a payload carrying control bytes is
    not a seed somebody wrote, whatever it decodes to.
    """
    try:
        seed = seed_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not seed.strip():
        return None
    if any(ord(char) < 0x20 and char not in _TEXTUAL_CONTROLS for char in seed):
        return None

    return DerivedBrief(
        brief=seed,
        fields={"origin": "generation_seed", "promptRecorded": True},
        brief_hash=_sha256(seed),
    )
