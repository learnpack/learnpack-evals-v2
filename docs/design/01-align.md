> ⚠️ **HISTORICAL SNAPSHOT (Jul-2026)** — design that produced slice 1 (human MVP). The current
> design is the series **`09-align-discover-qa.md` … `12-define-qa.md`** (internal QA). **Do not
> use this doc as a source for new code.**

# 01 — Align

> Step 1 of the DDD Starter Modelling Process (ddd-crew). State: **closed (v0, living)**.
> Phases of the process: Understand → **Align** → Discover → Decompose → Strategize →
> Connect → Organise → Define → Code. Iterative: Discover→Organise is repeated before
> Define; Define and Code can go in parallel.

## Product vision

A system to **evaluate the pedagogical quality of educational content generated (fully or
partially) by generative AI**. It evaluates content of different formats and origins,
through different **evaluation sources** (human SME, LLM-as-judge, deterministic
verifiers, hybrids) and under different **pedagogical criteria/approaches**, in a modular
and interchangeable way. It produces traceable and comparable quality judgments
(score + evidence/comment), and allows **calibrating and validating** automatic
evaluations against a human reference.

## What the core is (and what it is NOT)

- **Core = pedagogical evaluation.** The meaning of "pedagogical quality", the criteria/
  rubrics, the production of a judgment, and the representation of multiple **sources** and
  **approaches**. That is where the differentiator lives.
- **Calibration is NOT the core.** It is a *supporting* subdomain that feeds the core. The
  human evaluation of the MVP is simply *one source (HumanExpert) exercising the core*,
  wrapped in orchestration (assigning courses, viewing pending items).

## Strategic framing (input for step 4, Strategize)

- **Core** → *Pedagogical Evaluation*: criteria/rubrics, production of judgments, taxonomy
  of sources, grounding in frameworks, measurement/score separation.
- **Supporting** → Evaluation Orchestration (campaigns, assignments, pending items) ·
  Golden Dataset management · Calibration.
- **Generic** → Identity/users · Content registry & metadata · Notifications ·
  Projections/reporting · Localization (i18n).

## Two horizons (do not confuse them in the implementation)

1. **Target model** — modular app, interchangeable sources/criteria, modular monolith
   + domain events (evolvable to microservices). It is **designed in full** even if it is not
   implemented yet.
2. **MVP slice** — human evaluation tool to build the golden dataset, as lightweight as
   possible (Google Sheets as store if it speeds things up), no paid deploys, ready in
   hours. It is a **thin vertical slice** consistent with the target model, without the full
   clean-architecture ceremony. The docs preserve the north star; the code grows toward it.

> ⚠️ Risk to avoid: trying to build the complete modulith in hours. The MVP is
> deliberately simple; quality is guaranteed by the documented boundaries, not by
> premature ceremony.

## MVP scope (prioritized features)

Absolute priority: **that people can evaluate courses and that this data gets saved.**
Projections/reports can come later.

- Create a golden dataset of ~50 e-learning courses (lightweight registry: `GeneratingSystem`,
  external id, consumable url, metadata to be defined, own id). Without storing the full
  content.
- Register evaluators and assign courses to them (`Assignment`).
- Define the list of questions (= `LearnPack Pedagogical Rubric v1`, 5 criteria).
- Evaluator flow (3 steps): 1) view metadata · 2) access the content (url; iframe if
  viable) · 3) answer the form (5 criteria, mandatory score 1–5 + optional comment,
  with hints of what 1 is and what 5 is).
- Persist responses (which evaluator, which course, which scores).
- Admin views: who evaluated what / pending items; scores per course (individual and averages).

## Recorded decisions and constraints

- **Language:** ubiquitous language and code in **English**; docs and dialogue in Spanish.
- **UI i18n:** goal EN/ES; **MVP English-only**.
- **LearnPack:** content accessible via a url like
  `https://introduction-to-generative-ai.learn-pack.com/`; metadata by hand for now.
  Risk to verify in the Code step: `X-Frame-Options`/`CSP frame-ancestors` may
  block the iframe → fallback "open in new tab".
- **Evaluators:** internal and external SMEs, varied expertise; simple identification for
  the MVP (no robust auth).
- **Costs:** no paid deploys in the first version.

## Conceptual modelling agreed in Align

See `../GLOSSARY.md`. Key points governing the design:

1. **Framework as grounding, not as container.** `Criterion` cites frameworks (N:M);
   the frameworks/dimensions/qualities are *versioned reference data*, not hardcoded
   (the team can change them).
2. **Orthogonal and interchangeable axes:** `Content` (what) · `Criterion`/`Rubric` (what is
   measured) · `EvaluationSource` (how it is produced). With a compatibility relation
   `eligible_sources` between `Criterion` and `Source`.
3. **`EvaluationSource` is a port with 4 adapters:** HumanExpert, LLMJudge,
   DeterministicVerifier, HybridVerifier ("Hybrid Norm").
4. **Measurement ≠ judgment:** deterministic/hybrid sources produce `ComputedMetric`
   (raw signal) which a `ScoringPolicy` maps to `CriterionScore`; human/LLM score
   directly. See `research/deterministic-evaluation-landscape.md`.
5. **The `criterion` is the join key of calibration:** the same rubric scored by
   different sources allows comparing automatic vs. human reference per criterion.

## Business model (lightweight canvas)

- **Value proposition:** traceable, comparable and auditable pedagogical-quality
  judgments on AI-generated content, with interchangeable sources (human/
  automatic) calibratable against a human reference.
- **Users:** admin (curator/calibrator) · SME evaluators · (future) consumers of
  quality reports; generating systems as the origin of the content (LearnPack).
- **Immediate key activity:** build the human golden dataset (source of truth for
  calibration).
- **Constraints:** time (hours for the MVP), cost (no paid deploys).

## State and next step

- Align: **closed**.
- Next: **02 — Discover** (Big-Picture EventStorming of the evaluation domain, with
  the 4 sources as parallel branches and `LLMJudge`/`Calibration` included even though they
  do not enter the MVP). The MVP slice will come out as a cut of that timeline.
