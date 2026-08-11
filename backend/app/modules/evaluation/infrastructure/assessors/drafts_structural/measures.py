"""Measures this assessor computes over profile data — `ComputedMetric` values, not
outcomes (ADR-0010: the criterion's pass condition is what turns one into pass/fail).

They live inside the assessor and not in the extraction adapter on purpose: a derived
number is not something the package SAYS, and the `ContentProfile` is the citable evidence
base that stays free of inference (ADR-0009). The other half of the reason is versioning —
the only place in the model that gives an algorithm an identity is the assessor's version
(ADR-0016), so **any change in this file is a new version of `drafts-structural`**, and
calibration does not carry across it.

This file is a COPY of `structural` v1's measures, not an import, on purpose: a shared
module would tie two assessors' identities together, and a change to it would silently
change both artifacts. Editing this file says nothing about `structural`, and vice versa.

`docs/MEASUREMENT.md` holds the evidence behind what is measured here and behind what was
tried and rejected. Read it before changing a constant: the thresholds are empirical, set
against the frozen corpus, and the rejected alternatives were rejected with measurements.
"""

import re
from typing import Any

# Anything that is not the prose a learner reads. Fenced code and image alt text are
# removed before words are counted: a code block is not prose, and LearnPack's generated
# illustrations carry their whole image-generation prompt as alt text.
_FENCE = re.compile(r"```.*?```", re.S)
_IMAGE = re.compile(r"!\[.*?\]\([^)]*\)", re.S)
_INLINE_CODE = re.compile(r"`[^`]*`")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HEADING = re.compile(r"^#{1,6}\s")
_LIST_MARKER = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")
_EMPHASIS = re.compile(r"\*\*|__|\*|_")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")

_VOWELS = "aeiouy"

# Below this, the mean is dominated by whichever few words the lesson happens to use, so a
# short lesson neither sets a course's median nor gets accused of breaking it.
MIN_WORDS_FOR_A_STABLE_MEAN = 100


def _syllables(word: str) -> int:
    """Vowel groups, silent final -e, never fewer than one — the common heuristic.

    Approximate by construction: no syllable counter agrees with every dictionary. What
    matters for the criterion built on this is that it treats every lesson of a course the
    same way, and that the threshold it feeds is far larger than the disagreement between
    reasonable counters (docs/MEASUREMENT.md)."""
    letters = re.sub(r"[^a-z]", "", word.lower())
    if not letters:
        return 0
    count, previous_was_vowel = 0, False
    for character in letters:
        is_vowel = character in _VOWELS
        if is_vowel and not previous_was_vowel:
            count += 1
        previous_was_vowel = is_vowel
    if letters.endswith("e") and not letters.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def _prose_words(body: str) -> list[str]:
    """The words of a lesson's prose, in order. Headings are dropped (a heading is a label,
    not prose); list markers and emphasis are stripped, leaving the words untouched."""
    text = _LINK.sub(r"\1", _INLINE_CODE.sub(" ", _IMAGE.sub("\n", _FENCE.sub("\n", body))))
    words: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _HEADING.match(stripped) or set(stripped) <= set("-*_ "):
            continue
        words.extend(_WORD.findall(_EMPHASIS.sub("", _LIST_MARKER.sub("", stripped))))
    return words


def lexical_load(body: str) -> float | None:
    """Mean syllables per word over a lesson's prose — `None` when too short to be stable.

    This is the surviving half of Flesch-Kincaid. The other half, words per sentence,
    depends on where a sentence ends, and in markdown that is genuinely unsettled: bullets
    and headings carry no terminal punctuation, so two defensible segmenters disagree by
    more than the effect being measured. Syllables per word does not ask the question at
    all. See docs/MEASUREMENT.md for the measurements behind that choice.

    It measures VOCABULARY DENSITY, not cognitive demand: a hard idea in short words does
    not register here, and a plain lesson full of long domain nouns does. That is why the
    criterion compares a lesson to its own course rather than to an absolute band — the
    absolute level tracks subject matter."""
    words = _prose_words(body)
    if len(words) < MIN_WORDS_FOR_A_STABLE_MEAN:
        return None
    return sum(_syllables(word) for word in words) / len(words)


def lexical_load_by_lesson(bodies: list[dict[str, Any]]) -> dict[str, float]:
    """The measure per lesson slug, skipping the lessons too short to carry one."""
    measured = {}
    for lesson in bodies:
        value = lexical_load(str(lesson["body"]))
        if value is not None:
            measured[str(lesson["lessonSlug"])] = value
    return measured
