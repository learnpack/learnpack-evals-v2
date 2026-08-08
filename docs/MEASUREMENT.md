# Measurement — what the engine computes, and where its thresholds come from

Some criteria are decided by a number: a count, a ratio, an index over the text. This document
says **where such a number is computed, what each one means, and on what evidence its threshold
was set** — so that a threshold is never a figure someone once liked, and so that a measure that
was tried and rejected is not tried again.

Its companion is `GLOSSARY.md` (`ComputedMetric`, `CriterionScore`), which defines the terms this
document uses.

## Where a measurement is computed

A `ComputedMetric` is a **raw measurement**, not an outcome: the criterion's pass condition is
what turns it into `pass`/`fail` (ADR-0010). Measurements are computed by the **assessor**, never
by the extraction adapter. Two reasons, and both are load-bearing:

- **The `ContentProfile` stays free of inference (ADR-0009).** The profile is the citable evidence
  base — every entry quotes the package verbatim, with a locator anyone can check. A derived
  number is not something the package says, so it does not belong there.
- **The algorithm's identity is the assessor's version (ADR-0016).** Any change to a measurement —
  a different syllable heuristic, a different tokenizer — makes a *different* assessor, and
  calibration does not transfer across that boundary. There is nowhere else in the model that
  gives an algorithm a version.

So the split is: **what a measure means belongs to the instrument's criterion; how it is computed
belongs to the assessor's version.** An instrument can say "lexical load must not spike" without
committing anyone to one implementation of it.

## Readability

### What a LearnpackV1 package offers

Every lesson body opens with frontmatter carrying `readingTime.{minutes, words}` and
`fkglResult` — a Flesch-Kincaid Grade Level computed by LearnPack's own pipeline. It looks like a
free readability metric. **It is not used, and neither is a recomputation of it.** What follows is
why, because the temptation to wire it up is real.

### Why the declared value is not evidence

The declared metrics are a snapshot taken when the lesson was generated, not a property of the
file that ships. In the calibration corpus:

- `readingTime.words` matches the delivered body in **2 of 11** lessons of
  `object-representation-in-python`, and misses by up to 192 words elsewhere. No tokenization
  reconciles it.
- Three of that package's Spanish translations carry metrics **identical byte for byte** to their
  English counterparts, while the Spanish bodies run 4–25% longer. Both cannot be true.
- Of its eleven translated files, six carry empty frontmatter (`{}`) and two carry none.

The metrics were computed before later pipeline steps — illustration, translation, edits — rewrote
the text around them.

A stale declared metric is a **pipeline hygiene** problem, not a pedagogical one. It is
deliberately not made into a criterion: the instrument asserts about the pedagogical quality of
what a generator produces, and a criterion measuring metadata freshness would put a different kind
of signal into the same fitness denominator (ADR-0023).

### Why recomputing Flesch-Kincaid does not rescue it

FKGL is `0.39·(words/sentence) + 11.8·(syllables/word) − 15.59`. The first term depends on **where
a sentence ends**, and in markdown that is not a settled question: bullet items and headings carry
no terminal punctuation, so a segmenter either merges a whole list into one enormous sentence or
treats each item as a complete one. The two readings are both defensible and they disagree
sharply.

Comparing the two over the corpus — the metric is the highest lesson's grade above its own
course's median:

| Package | merge-lists reading | split-lists reading | verdict at +3 |
|---|---|---|---|
| `ai-concepts-an-exploration-inside-ai` | +2.87 | +4.47 | **disagree** |
| `html-fundamentals` | +3.89 | +3.28 | agree (fail) |
| `introduction-to-generative-ai` | +1.89 | +2.59 | agree (pass) |
| `object-representation-in-python` | +5.09 | +3.39 | agree (fail) |
| `orchestrating-a-multi-agent-system-in-langgraph` | +3.66 | +2.26 | **disagree** |

**Two of five packages change verdict on a modelling choice with no pedagogical content.**
Thresholds from 2 to 5 were tried: every one either leaves disagreements or is so high the
criterion never fires. Pinning one segmenter would buy *reproducibility* — the same number every
run — but not *validity*: the answer would still be as much about how a bullet list is read as
about the text.

### What is measured instead: `lexical_load`

Dropping the unstable term leaves the stable one. **`lexical_load` is the mean number of syllables
per word** over a lesson's prose, with fenced code, image alt text and headings excluded. It does
not depend on sentence segmentation at all, because it never asks where a sentence ends.

The same comparison, under two modelling variants (headings dropped or kept):

| Package | variant 1 | variant 2 | verdict at 0.20 |
|---|---|---|---|
| `ai-concepts-an-exploration-inside-ai` | +0.318 | +0.348 | agree (**fail**) |
| `html-fundamentals` | +0.095 | +0.113 | agree (pass) |
| `introduction-to-generative-ai` | +0.137 | +0.141 | agree (pass) |
| `object-representation-in-python` | +0.243 | +0.266 | agree (**fail**) |
| `orchestrating-a-multi-agent-system-in-langgraph` | +0.221 | +0.236 | agree (**fail**) |

Five of five agree, the largest divergence is **0.03** against a threshold of **0.20** — a margin
of roughly seven times — and the measure still separates the corpus three to two. That margin is
the point: **a threshold must be larger than the disagreement between reasonable implementations,
or the criterion is decided by the implementation.**

### Why it is compared to the course, not to a band

Each lesson is compared to **the median of its own course**, never to an absolute level. Median
lexical load by package runs from 1.575 (`html-fundamentals`) to 1.788
(`introduction-to-generative-ai`) — a spread of 0.21, **wider than the within-course threshold**.
An absolute band would therefore mostly measure subject matter: writing about neural networks uses
longer words than writing about HTML tags, and that is not a defect. Comparing a lesson to its own
course cancels the domain out.

### What `lexical_load` does not tell you

- It measures **vocabulary density, not cognitive demand**. A text can be conceptually hard in
  short words.
- It is **English-only**. The syllable-per-word baseline differs by language for reasons of
  language, not difficulty. A criterion built on it declares `condition: {content_language: en}`
  and the format's binding declares the matching task variable, so under a binding for
  non-English content the criterion derives `not_applicable` mechanically (ADR-0018: that outcome
  comes from applicability and capability, never from an executor's runtime decision) instead of
  reporting the language as a defect. The granularity is the binding, not the individual package:
  a package whose bodies are not in the language its binding declares would still be measured.
- **Short lessons give unstable averages**, so very short bodies are excluded from the comparison
  rather than allowed to set or break a course's median.
- It is a **proxy awaiting calibration against the human reference** (ADR-0015). Until that
  happens it is a signal worth surfacing, not a verdict worth defending.

### Rejected, and not worth retrying

- **An absolute FKGL band** ("no lesson above grade 12 in a beginner course"). The disagreement
  between implementations is larger than the band's own tolerance.
- **Extracting the declared `fkglResult` as corroboration.** See above: metadata freshness is not
  pedagogical quality.
- **A lesson-length balance criterion** over word counts. With sane thresholds it never fires
  anywhere in the corpus (the widest spread is 1.80× the median against a 3× threshold); tightened
  until it does fire, it flags `ai-concepts 05.1`, a lesson that is brief but complete — causes,
  examples, consequences, mitigations and a closing note. A criterion that only fires on healthy
  content is worse than no criterion.

## Thresholds in force

| Measure | Criterion | Threshold | Basis |
|---|---|---|---|
| `lexical_load` | `cr-no-lesson-spikes-in-lexical-load` | course median + **0.20** | Corpus: all five packages agree under two modelling variants, max divergence 0.03; separates the corpus 3/2 |

Every threshold here is set against the frozen calibration corpus in
`backend/tests/fixtures/learnpack_v1/`, and a test pins the verdict each package produces.
**Changing that set changes what these numbers mean** — recalibrate rather than assume they carry
over.
