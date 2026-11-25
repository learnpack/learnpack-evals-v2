# ADR-0069 — The console speaks the GLOSSARY: one word per concept

**Status:** accepted · **Date:** 2026-11 · **DDD context:** cross-cutting (console)

## Context

The GLOSSARY is where code names come from (`CLAUDE.md`), and the code follows it. The console's
copy does not. It was written screen by screen, and each screen reached for whatever word read
best in its own sentence, so the same concept now appears under several names, sometimes on the
same screen:

| Concept | Words the console shows |
|---|---|
| `EvaluationStudy` | *study*, *round* |
| an automated `Assessor` | *assessor*, *judge* |
| `GenerationBrief` | *brief*, *commission* |
| `ContentProfile` | *Profiles*, *Content profiles* |

A reader who knows the model translates these without noticing. A reader who does not cannot
tell whether *round* and *study* are two things or one, and the console is where most people
first meet the model. Two other habits make it worse. Identifiers such as
`cr-no-lesson-spikes-in-lexical-load` are often the main text of a row, with the sentence they
stand for hidden in a tooltip. And on-screen copy cites ADRs and internal settings to justify
itself: that explains a design to whoever maintains it and tells a reader nothing.

The GLOSSARY has the same fault in one place: it calls the `GenerationBrief` "the generation
commission" and the `EvaluationStudy` "the commission". One word, two concepts.

A plainer vocabulary for the console was considered and rejected (below). ADR-0043 §8 has
already settled the principle: "a label that disagrees with its model is the same defect" a
rename removes.

## Decision

**The console shows exactly one word for each concept, and it is the GLOSSARY's word.**

1. **The visible word is the GLOSSARY's.** A study is a *study*, never a *round*. An automated
   assessor is an *assessor*, never a *judge*. A brief is a *brief*, never a *commission*. A
   synonym that has been used for convenience is removed, not added to a list of accepted
   alternatives. *Evaluator* stays: it is the role the model gives a human assessor
   (ADR-0049, ADR-0050), not another word for the assessor. *Expert* is not a name for
   anything in the model either: the console uses it only to say who evaluators are,
   subject-matter experts, in the *Experts* heading and the *Ask experts* task, as the README
   does. A rubric stays a *rubric*, its GLOSSARY name; *reference instrument* is the role it
   plays, and documents may say so in a sentence but do not use it as a second name.
2. **A term the reader may not know carries a short definition where it appears.** It is one
   plain sentence, written as console copy and kept beside the code that shows it. The full
   definition stays in the GLOSSARY, and the short one points to it rather than restating it.
3. **An identifier is secondary text.** Where a claim, criterion or instrument version is
   shown, its sentence or name is the main text. The id follows it in a smaller, monospaced,
   copyable form, because cross-referencing the YAML is a real need, only a different one.
4. **On-screen copy does not explain the design.** It cites no ADR and no internal setting
   to justify itself. Where a maintainer needs the reason, it goes in a `title` or a code
   comment. An instruction the reader has to follow is not an explanation and stays: a command
   to run, or a setting to configure for an act the console cannot do itself.
5. **Three things keep their words:** the backend's error messages, which the console relays
   verbatim; anything frozen in a published report (ADR-0041); and the pedagogical names of
   the decision mechanisms in `docs/MEASUREMENT.md` ("model judges" names a mechanism, not
   an assessor).
6. **The GLOSSARY's own collision is fixed.** Neither the `GenerationBrief` entry nor the
   `EvaluationStudy` entry calls itself "the commission" any more, and the GLOSSARY's other
   definitions stop saying *round* for a study. Each entry notes the older word once ("older
   documents call it…"), which is what lets a reader of an immutable ADR resolve it.
7. **A newcomer's first documents follow the same rule.** The root `README.md` and
   `docs/RUNBOOK-measuring.md` drop *round*, *judge* and *commission* as nouns. They are the
   first two documents a newcomer reads, and teaching a synonym there would undo the console.

## Consequences

- (+) A reader meets each concept under one name, in the console and in the GLOSSARY, and
  can look that name up.
- (+) No second vocabulary to keep in step: the console's words are the model's words, so a
  rename in the model (ADR-0043 §8) is a rename in the console and nothing else.
- (−) Some formal words are less inviting than the synonyms they replace (*assessor* against
  *judge*). The short definitions in clause 2 carry that cost.
- (−) Older ADRs and frozen design snapshots keep using *round* and *commission*. They are
  immutable (`CLAUDE.md`), and a reader who meets them there has the GLOSSARY to resolve
  them.

## Alternatives considered

- **Plain labels that differ from the model** (*Judge* for an automated assessor, *Expert* for
  a human one), with the formal name in a tooltip. Rejected: it creates the disagreement
  ADR-0043 §8 calls a defect, and two of the candidates (*judge*, *evaluator* as a generic
  scorer) are evals-industry terms that `CLAUDE.md` keeps out of domain names
  (`GLOSSARY.md`, "Equivalences with the evals industry").
- **Leave each screen to choose.** Rejected: that is the current state, and it produced the
  table in the Context.
- **A mapping table of console labels inside the GLOSSARY.** Rejected together with the first
  alternative: with no labels that differ from the model, there is nothing to map.

## References

ADR-0043 §8 (a label agrees with its model) · ADR-0041 (what a published report froze is not
rewritten) · ADR-0049, ADR-0050 (*evaluator* is a role) · `CLAUDE.md` (code names come from the
GLOSSARY; industry terms stay in the equivalences table) · `docs/MEASUREMENT.md` (the decision
mechanisms).
