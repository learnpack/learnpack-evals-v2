# Measurement — what the engine computes, and where its thresholds come from

Some criteria are decided by a number: a count, a ratio, an index over the text. Others are
decided over what a model read, and some by a model outright. This document says **how each
criterion is decided** by the assessors the workbench registers, and, for the ones decided by a
number, **where that number is computed, what it means, and on what evidence its threshold was
set** — so that a threshold is never a figure someone once liked, and so that a measure that was
tried and rejected is not tried again.

Its companion is `GLOSSARY.md` (`ComputedMetric`, `CriterionScore`), which defines the terms this
document uses.

## How each criterion is decided

A criterion says **what** is verified; the assessor's version says **how** (ADR-0016). The
mechanism is an internal detail of the assessor and never part of the criterion: the same
criterion can be decided by code in one assessor and by a model in another, and moving it from one
to the other is a new assessor version. So what follows describes **assessors**, not instruments.

Whatever the mechanism, an executed criterion ends the same way — `pass` or `fail`, with a verbatim
quote and its locator (ADR-0009). It gets there in one of three ways, or the assessor declines it:

- **deterministic** — code over the profile: a count, a presence or order check, a measure such
  as `lexical_load` (below). No model is called, and the same profile always gets the same
  verdict.
- **model extracts, code decides** — a model reads the course and returns *data*: the outcomes
  the opening lesson states, the cognitive level of each objective, which tasks bear on which
  objective, where each concept is stated and what each module does with it. Every item is
  grounded — a quote checked verbatim against the text, or an identifier from a closed list — and
  the pass condition is applied to it in code: a count, an order, a trajectory rule. The model
  supplies data, never the verdict.
- **model judges** — the pass condition has no mechanical proxy ("does the closing lesson
  integrate what the course taught?"), so the model answers with the verdict itself, asked with
  the instrument's `pass_condition` and failure modes verbatim. The answer must cite a passage
  that is checked against the text; it is asked twice, a third time only when the two disagree,
  and the majority is taken in code. A criterion about several objectives is answered one
  objective at a time and added up in code.
- **abstains** — the assessor declares that it does not decide the criterion (ADR-0018). The
  criterion derives `not_assessed`, leaves the denominator, and is left to a human.

An assessor that decides anything through a model calls it through OpenRouter, so measuring with
it needs `LLM_API_KEY` (`backend/README.md`).

The labels are read off the code, not off its comments: `backend/tests/test_decision_mechanisms_doc.py`
walks each executor's calls and fails as soon as a table below stops matching the registry.

### By assessor

The instrument is the version the workbench publishes for the assessor's lineage
(`docs/seed/workbench.yaml`).

| Assessor | Instrument | Criteria | deterministic | model extracts, code decides | model judges | abstains |
|---|---|---|---|---|---|---|
| `structural` v1 | `learnpack-course-qa-v1` | 27 | 9 | 0 | 0 | 18 |
| `drafts-structural` v1 | `course-drafts-qa-v10` | 30 | 7 | 0 | 0 | 23 |
| `drafts-hybrid` v13 | `course-drafts-qa-v10` | 30 | 7 | 9 | 5 | 9 |

### Criterion by criterion: `drafts-hybrid` v13 over `course-drafts-qa-v10`

In the instrument's order. The last column does not depend on the assessor: it says whether the
derivation lets the criterion reach **any** assessor on a `LearnpackV1` course. That format's
adapter supplies no declared objectives, audience, prerequisites, per-lesson concepts or proposed
assessment, so a criterion that requires one of them derives `not_applicable` there (ADR-0018) —
reading them out of the lesson bodies would be inference (ADR-0009).

| Criterion | How it is decided | On a `LearnpackV1` course |
|---|---|---|
| `cr-objectives-min-count` | deterministic | not applicable |
| `cr-objectives-observable-verbs` | model extracts, code decides | not applicable |
| `cr-outcomes-present` | model extracts, code decides | runs |
| `cr-outcomes-observable-verbs` | model extracts, code decides | runs |
| `cr-objectives-verb-level-band` | abstains | runs |
| `cr-objectives-non-decreasing-demand` | model extracts, code decides | not applicable |
| `cr-every-objective-is-developed-somewhere` | abstains | not applicable |
| `cr-every-substantive-lesson-serves-an-objective` | abstains | not applicable |
| `cr-lesson-works-at-the-level-its-objective-demands` | abstains | not applicable |
| `cr-every-objective-has-an-assessment-item` | model extracts, code decides | not applicable |
| `cr-assessment-matches-the-declared-verification` | model judges | not applicable |
| `cr-new-instruction-is-preceded-by-a-problem` | abstains | runs |
| `cr-opening-lesson-connects-backwards` | model judges | runs |
| `cr-closing-lesson-integrates` | model judges | runs |
| `cr-closing-lesson-projects-forward` | model judges | runs |
| `cr-skill-lessons-carry-a-worked-example` | abstains | runs |
| `cr-course-opens-with-general-intro` | deterministic | runs |
| `cr-course-has-development` | deterministic | runs |
| `cr-arc-character` | model judges | runs |
| `cr-lessons-build-within-their-module` | model extracts, code decides | not applicable |
| `cr-modules-build-on-earlier-modules` | model extracts, code decides | not applicable |
| `cr-assessment-retrieves-earlier-taught-material` | model extracts, code decides | not applicable |
| `cr-module-structure-well-formed` | deterministic | runs |
| `cr-module-single-topic` | abstains | runs |
| `cr-adjacent-pair-has-a-bridge` | abstains | runs |
| `cr-concepts-introduced-before-use` | abstains | runs |
| `cr-audience-declared` | deterministic | not applicable |
| `cr-prerequisites-declared` | deterministic | not applicable |
| `cr-no-lesson-spikes-in-lexical-load` | deterministic | runs |
| `cr-cognitive-demand-rises-across-the-course` | model extracts, code decides | not applicable |

Why each abstention is one is written next to it, in the assessor's `ABSTENTIONS`
(`backend/app/modules/evaluation/infrastructure/assessors/drafts_hybrid/__init__.py`).

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

### How it is computed

In `backend/app/modules/evaluation/infrastructure/assessors/<name>/measures.py`, and
therefore versioned with that assessor: changing any of the following is a **new assessor**,
even when no criterion's wording moves.

**There is one such file per assessor that executes the criterion, and they are deliberately
copies rather than a shared module** (ADR-0016: sharing would tie two assessors' identities
together, so one edit would silently change both artifacts). Editing one says nothing about
the others, which is the point — and it is also the trap: a correction made in one place
leaves every other assessor computing the old measure, and nothing warns you. If a change is
meant to apply to all of them, it is that many version bumps.

1. **What counts as prose.** Fenced code blocks and image alt text are removed before
   anything is counted — a code block is not prose, and LearnPack's generated illustrations
   carry their entire image-generation prompt as alt text, hundreds of words of it. Inline
   code is dropped, link text is kept and its target discarded, headings are skipped (a
   heading is a label), and list markers and emphasis are stripped without touching words.
2. **Syllables per word**, counted by the usual heuristic: vowel groups, silent final `-e`,
   never fewer than one. Approximate by construction — no counter agrees with every
   dictionary. What the criterion needs is that every lesson of a course is treated the same
   way and that the threshold is far larger than the disagreement between counters.
3. **A lesson under 100 words is skipped**, neither setting the course median nor being
   accused of exceeding it: below that the mean is decided by whichever few words the lesson
   happened to use. No lesson in the calibration corpus falls under the guard, so the numbers
   below come from every lesson of every package.

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

What each package of the corpus produces:

| Package | median | worst lesson, above the median | at 0.20 |
|---|---|---|---|
| `ai-concepts-an-exploration-inside-ai` | 1.716 | +0.318 (`05.1-hallucinations-in-ai`) | **fail** |
| `html-fundamentals` | 1.575 | +0.095 | pass |
| `introduction-to-generative-ai` | 1.788 | +0.137 | pass |
| `object-representation-in-python` | 1.656 | +0.243 (`02.1-dot-notation`) | **fail** |
| `orchestrating-…-langgraph` | 1.725 | +0.221 | **fail** |

Every threshold here is set against the frozen calibration corpus in
`backend/tests/fixtures/learnpack_v1/`, and `backend/tests/test_calibration.py` pins the verdict
each package produces. **Changing that set changes what these numbers mean** — recalibrate rather
than assume they carry over. The last package sits 0.02 above the line, so a careless change to
the measure flips it; that test exists to make the flip loud.

### The corpus is LearnpackV1, and the criterion no longer is

That corpus is five **LearnpackV1** packages: finished courses, whose lesson bodies are the
learner-facing text. The criterion has since been inherited by the `course-drafts-qa` lineage
and now also runs over **LearnpackV2 drafts**, which are a different artefact — what a
generator emits before a teacher processes it — and **nothing has been recalibrated against
them**. The 0.20 in force there is a number carried over, not a number measured.

That is a gap in the evidence, not a defect in the measure: `lexical_load` itself does not
depend on the format, and a threshold set on prose is not obviously wrong on other prose.
What is unknown is whether drafts spread the same way — whether their within-course median
and their worst lesson sit at the distances V1 courses do. Recalibrating means the same
exercise this document records: run the measure over a frozen set of drafts, check that
reasonable modelling variants agree, and check that the threshold separates the set instead of
passing or failing all of it. Until that is done, a `fail` on this criterion over a draft is
weaker evidence than the table above suggests, and it should be read with the lesson in hand.
