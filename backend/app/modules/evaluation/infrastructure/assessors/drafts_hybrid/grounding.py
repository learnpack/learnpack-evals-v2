"""Finding a model's citation in the text it was shown — the rule every task here shares.

A citation that cannot be found in the source is not evidence (ADR-0009), so every task that
asks for one validates it. What "found" means is this module, and it is deliberately not byte
equality: three differences are the model's rendering of our text rather than a claim about
the course, and refusing them costs a retry for nothing.

- **Whitespace is not content.** A corpus built by this package puts entries on their own
  indented lines, and a model quoting across one renders the newline and indent as a single
  space.
- **Neither is markdown emphasis.** Lesson bodies are markdown, so a sentence can carry
  `**bold**` or backticks, and a model quoting it drops the markers about as often as it
  keeps them.
- **Nor is the marker of a list item.** A quote that runs from a lead-in into the list under
  it is the common shape, and the model may or may not carry the bullet across — the source
  has it at the start of a line, the quote has it mid-sentence after a space. Both readings
  are faithful, so the marker is invisible **wherever a break puts it**: at the start of the
  text or after whitespace, on both sides of the comparison. Making it invisible only at the
  start of a line is what a first attempt did, and it turned the false negative around
  instead of removing it — a model that copied the bullet was then the one refused.

What is returned is always the SOURCE's own span, never the model's rendering: tolerating a
difference when matching is not the same as storing it, so the passage a report shows is the
course's text — emphasis markers, bullets and all — and ADR-0009 stays exact.

Shared by `tasks.py` and `judgments.py` rather than living in either: the extraction tasks
demand verbatim statements and the judged ones demand verbatim passages, and two copies of
this rule would be two definitions of what counts as a citation.
"""

import re

# Markdown emphasis, dropped when matching a quote against its source. Skipping `_` is the
# one that can bite in the other direction: it makes `lesson_bodies` and `lessonbodies` equal
# for the search. Accepted — it is a false positive in the direction we already chose to
# tolerate, and reaching it needs the model to delete an underscore, which is a formatting
# edit rather than an invention.
_EMPHASIS = frozenset("*_`")

# What opens a list item: a bullet or an ordinal followed by a space, at a point where a break
# already put us. The trailing space is what keeps this narrow — `-3 degrees` opens nothing and
# `1.5 seconds` is not an ordinal — and matching only after a break keeps `well-formed` intact.
_LIST_MARKER = re.compile(r"(?:[-*+]|\d{1,3}[.)])[ \t]+")


def locate(corpus: str, quote: str) -> str | None:
    """The corpus's OWN span matching `quote` under the tolerances above, or `None`."""
    flat_corpus, offsets = flatten(corpus)
    flat_quote, _ = flatten(quote)
    if not flat_quote:
        return None
    at = flat_corpus.find(flat_quote)
    if at < 0:
        return None
    return corpus[offsets[at] : offsets[at + len(flat_quote) - 1] + 1]


def flatten(text: str) -> tuple[str, list[int]]:
    """`text` with whitespace runs collapsed to one space, emphasis and list markers dropped
    and the ends stripped, plus, per character kept, the index it came from — which is what
    lets a match map back to the original."""
    kept: list[str] = []
    offsets: list[int] = []
    after_space = True
    index = 0
    while index < len(text):
        if after_space:
            # A break — the start of the text or the whitespace just emitted — is the only
            # place a list marker can open, and both sides of the comparison are read the
            # same way, so it does not matter whether the break was a newline or a space.
            marker = _LIST_MARKER.match(text, index)
            if marker is not None:
                index = marker.end()
                continue
        char = text[index]
        index += 1
        if char in _EMPHASIS:
            # Not touching `after_space` on purpose: an emphasis marker is invisible, so
            # `**a** **b**` still flattens to `a b` rather than `ab`.
            continue
        if char.isspace():
            if not after_space:
                kept.append(" ")
                offsets.append(index - 1)
                after_space = True
            continue
        kept.append(char)
        offsets.append(index - 1)
        after_space = False
    if kept and kept[-1] == " ":
        kept.pop()
        offsets.pop()
    return "".join(kept), offsets


def grounding_violations(label: str, quote: str, corpus: str) -> list[str]:
    """Why this quote is not evidence — naming the RULE that was broken, not just the fact.

    The generic "not verbatim" message cost a whole evaluation once: the model had joined real
    passages with "..." and, told only that its quote was not verbatim, answered the same thing
    three times, because from where it stood every fragment WAS copied. Feedback has to name
    what to do differently.
    """
    if locate(corpus, quote) is not None:
        return []
    if "..." in quote or "…" in quote:
        return [
            f"{label} joins separate passages with an ellipsis. Each entry of "
            '"evidence" must be ONE CONTINUOUS passage copied from the text: split it '
            "into several entries instead, one per place in the text."
        ]
    return [
        f"{label} is not a passage from the text shown — copy it character-for-character "
        f"(got: {quote.strip()[:120]!r})"
    ]
