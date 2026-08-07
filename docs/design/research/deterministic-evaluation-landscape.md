# Research note — Landscape of deterministic / hybrid evaluation of pedagogical quality

> Design input gathered in Align (Jul-2026) to enrich the modelling of
> `EvaluationSource`, `ComputedMetric` and `eligible_sources`. Not exhaustive; a base
> for Discover/Define. All statements paraphrased; see sources.

## Central thesis

"Deterministic vs. rubric" **is not a dichotomy**: it is a spectrum of verifiers that are
**combined** (the "Hybrid Norm"): programmatic checks for the objective truths ("what"),
rubrics via LLM judge for the nuanced quality ("how"), and human oversight for
governance and calibration.

## Families of deterministic evaluation (or det. + LLM)

### 1. Readability — fully deterministic
Computable formulas: Flesch-Kincaid Grade Level, Gunning Fog, SMOG, ARI, Dale-Chall.
They estimate the school grade/years of education needed to understand a text. Cheap and
reproducible; medium correlation with human-perceived level → useful signal, not sufficient.
Applicable to: "readability appropriate for the target audience".

### 2. Cohesion and coherence — deterministic over linguistic features
Tools like Coh-Metrix / TAACO: dozens of indices (referential cohesion, connectives,
lexical overlap). Designed because readability formulas depend too much on
surface features; the indices are validated against expert coherence judgments.
Applicable to: "coherent sequencing", "cohesion of the material".

### 3. Cognitive level (Bloom / SOLO) — ML classification, today also LLM
Classifying objectives and questions by Bloom level is a mature task (classifiers
trained on tens of thousands of objectives); LLMs enable zero/few-shot.
Applicable to: "do the objectives cover high cognitive levels or only recall?".

### 4. Alignment (curricular and constructive) — embeddings / semantic matching
Semantic similarity objective↔content↔assessment with Sentence-BERT / DeBERTa / RoBERTa
(item-to-standard alignment with high F1). It operationalizes Biggs' triangle
(constructive alignment: objectives ↔ activities ↔ assessment) and the detection of
misalignment/item defects.
→ **Direct fit with `pgvector`.**
Applicable to: "constructive alignment", "objective coverage".

### 5. Presence/structure and progression — rule checks
"Blueprint"-style verifications: are there explicit objectives, examples, worked examples,
activities, assessment, feedback? Does the order respect prerequisites / learning progressions?
They map almost 1:1 to Merrill (First Principles) and Learning Progressions.
The **course metadata** (objectives, audience, prerequisites) is the *reference* of these
checks.

## The "Hybrid Norm" (key architectural pattern)

- **Programmatic** verifiers: deterministic, auditable, **never hallucinate**, with
  enumerable failure modes — but brittle.
- **LLM** judges: flexible but opaque; they inherit the model's biases.
- Observed fusion patterns: rule → binary signal or bounded base score that is later
  **fused** with the LLM judge; in code, LLM evaluates the logic and a deterministic
  compiler verifies the syntax, and the scores are **summed**.
- **Analytic rubrics** (criterion by criterion) > holistic ones (single, opaque score) →
  matches how we model `Rubric`.

## Modelling implications (carried into the model)

1. `EvaluationSource` = taxonomy of 4 adapters (HumanExpert, LLMJudge,
   DeterministicVerifier, HybridVerifier) behind a port.
2. Separate *what is measured* (`Criterion`, grounded) from *how it is produced* (`EvaluationSource`).
3. `eligible_sources` relation: some criteria are computable, others require judgment.
4. Introduce `ComputedMetric` (raw measurement) distinct from `CriterionScore` (judgment);
   `ScoringPolicy` maps metric→score, often against a threshold/reference from the metadata.
5. A gift for calibration: the deterministic ones can be run over the 50 courses already
   and correlated against the human golden per dimension. Caveat: deterministic ≠ valid
   (the formulas have known limits) → that is why the golden dataset exists.

## Sources (selection)

- COGENT — Curriculum-oriented framework, readability/comprehensibility/curriculum
  alignment triad (arXiv 2506.09367).
- Coh-Metrix / TAACO — automatic cohesion and coherence.
- Readability formulas — Flesch-Kincaid, Gunning Fog, SMOG, ARI, Dale-Chall.
- Bloom auto-classification — EDM 2022 (Monash, 21k objectives); BEA 2025 (Kolagar et al.);
  Almatrafi & Johri 2025 (GenAI for outcome categorization).
- Item↔standard alignment — DeBERTa/RoBERTa/Sentence-BERT (arXiv 2510.05129).
- Constructive alignment (Biggs) — objectives/activities/assessment triangle; alignment
  of MCQs to objectives (BMC Med Educ 2025; arXiv 2506.23815).
- Hybrid Norm / RLVR — programmatic vs. learned vs. hybrid verifiers
  (rlvrbook.com ch.4); RaR / RLCF; Autorubric (arXiv 2603.00077); KnowU-Bench hybrid
  (arXiv 2604.08455); "Rubric is all you need" (ICER 2025).
