# ADR-0013 — Evaluation design with ECD-lite: claims as the axis

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Rubric/Instrument Authoring ·
Pedagogical Evaluation · Reporting

## Context

There was no instrument design process: criteria were written directly, and the structural
decisions —what is intended to be measured, how much evidence suffices, what would invalidate an
observation— remained tacit. It is the exact diagnosis that ECBD (ACL 2024) makes of NLP
benchmarks: design resting on "tacit and untested assumptions about what is intended to be
measured".

**Evidence-Centered Design** (Mislevy et al.) structures an evaluation as an **evidentiary
argument**: *claim ← evidence accumulation ← observables ← evidence identification ←
work product ← task*, with **warrants** (Toulmin) licensing each inference and **alternative
explanations** that must be ruled out. ECBD demonstrated that ECD transfers to evaluating
AI systems. Its application to pedagogical quality of AI-generated content does not exist in
published form; this system occupies that intersection: **the examinee is the generator; each
content is a work product of it**.

ADRs 0009/0010/0011 already have ECD form without naming it: quoted evidence = evidence
identification; verifiable conditions = scoring rules; not collapsing to a number = a constraint
on accumulation.

## Decision

**ECD-lite is adopted: four pieces, not a rewrite.**

1. **`Claim` as a first-class artifact.** A claims register: one sentence + required
   evidence + warrant (framework) + alternative explanations. If a claim needs more than
   half a page, it is badly decomposed. **The design runs backwards**: claims → evidence →
   observables → extraction requirements. The data demand of the entire system originates here
   (see ADR-0014).
2. **Two grains of claims: content and generator.** In addition to the per-content judgment,
   evidence is accumulated **across contents** to assert patterns of the generator ("it
   systematically produces vague objectives in introductory courses"). The generator-level claim
   is the central product of internal QA.
3. **Alternative explanations by design.** Each claim enumerates *in advance* what could
   produce the same observation without the claim applying: failed extraction, atypical format,
   ambiguous criterion. It formalizes the diagnosis of the instrument improvement loop and the
   findings-challenge channel.
4. **Explicit assembly: how much evidence suffices, per claim, decided at design time.** On the
   automatic path it replaces the notion of quorum; replicating assessors is one way to strengthen
   evidence, coverage is another. **It does not supersede ADR-0002**: the human quorum still
   governs campaigns with human evaluators. Compatible with ADR-0006 (self-consistency ≠
   inter-rater).

**The report changes in nature:** claims with evidentiary status —`supported / refuted /
insufficient evidence`— with the findings organized **under the claim they compromise**. The
per-criterion tri-state (ADR-0010) propagates one level up by the same logic.

**Guards:**
- No statistical machinery (IRT, Bayesian networks): accumulation is simple and explicit.
- **"% of supported claims" is forbidden** as a score — ADR-0011 applies equally one level up: a
  claim is a qualitative assertion backed by specific evidence, not an average.
- No wholesale renaming of existing artifacts: the adoption's value lies in the four pieces.

## Consequences

- (+) Loose ends find a formal home: the `ScoringPolicy`'s "contextual reference" is a
  **task model variable**; the prioritization of findings comes from their claim; the
  *designed-for* (ADR-0012) is realized as a **task model binding** per content type, leaving
  claims and evidence models portable.
- (+) `Quality`/`PedagogicalDimension` ascend from reference data to **examinee model
  variables**: claims are assertions about them.
- (+) The **selection of the contentSet becomes a design decision** (ECBD's content module): "for
  evidence of progression, the set needs courses with chained prerequisites". It does not cross
  the system boundary — we do not generate; we choose what to evaluate.
- (−) One more artifact to maintain (the claims register). Cheap if the half-page limit is
  respected.
- (−) It demands discipline to stay *lite*: the temptation to over-formalize is real.

## Alternatives considered

- **Continue with rubric-first design, without claims** → rejected: tacit assumptions with no
  validity argument, and —decisively— no place for generator-level assertions, which are the
  product of internal QA.
- **Full ECD** (formal CAF, measurement models) → rejected: unjustified weight at this
  scale; the value lies in the explicit argument, not in the psychometric machinery.
- **Adopt ECBD in full (five modules)** → rejected: ceremony specific to public
  benchmarks; the conceptual core it shares with ECD is taken.

## References

ECBD (https://aclanthology.org/2024.acl-long.861/) · Mislevy, Implications of ECD
(https://csaa.wested.org/wp-content/uploads/2020/01/2006_Implications_of_Evidence_Centered_Design_for_Educational_Testing.pdf) ·
evidence identification vs. accumulation (https://files.eric.ed.gov/fulltext/EJ1115353.pdf) ·
detailed reasoning and full mapping in `notes/genesis-instrumentos-y-ecd.md`.
