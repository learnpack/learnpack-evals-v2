# Research note — Inputs of the internal QA redesign (slice 2)

> Dated external inputs (Jul–Aug 2026) that ground the 09–12 series and ADRs 0009–0015.
> Frozen; paraphrased statements, see sources. Complements
> `deterministic-evaluation-landscape.md` (Jul-2026).

## 1. How professional human teams evaluate pedagogical quality

Systems studied: EdReports (K-12 curricula), Quality Matters (online courses), EQuIP
(lessons/units), district adoption, editorial QA, norming/moderation.

- **Consistent process:** versioned instrument → certify/train reviewers (EdReports:
  25 h before touching material) → **norming** with anchors (one high and one low exemplar with
  failure modes) → **independent** evidence collection → argued consensus (not averaging)
  → escalation (two reviewers → chair → third rater) → report with evidence → response from the
  evaluand → re-review of the delta → feedback into the instrument.
- **The instrument is two documents:** Review Criteria + **Evidence Guide** (how to collect
  evidence, per indicator) — the extraction/judgment separation exists in the human world.
- **Disagreement is diagnostic:** its root causes (ambiguous criterion, insufficient evidence,
  training, knowledge that changed) call for different corrections — high discrepancy
  signals a badly written criterion.
- **Versioning:** EdReports v2.0 does not re-issue old reports ("does not update retroactively") —
  origin of our pinning rule.
- **Business:** EdReports' credibility = structural independence (it does not charge evaluands);
  the value of the service is not the score but **the change it produces** (40+ publishers adjusted
  products). In internal QA, independence is replaced by **traceability to evidence**.
- Composition: **sequential gateways** (EdReports) and **QA layers** (editorial); Quality
  Matters adds **mandatory gates** (essentials that must all be met) — the simple mean
  is the weakest aggregation.

Sources: edreports.org/process · qualitymatters.org/why-quality-matters/process ·
achieve.org (EQuIP) · scu.edu (norming) · pubmed 12147915 (third-rater adjudication).

## 2. Instrument design: ECD and ECBD

- **Evidence-Centered Design** (Mislevy): assessment as an **evidential argument** —
  claim ← accumulation ← observables ← evidence identification ← work product ← task; with
  warrants (Toulmin) and **alternative explanations**. The evidence model separates identification
  (product → observables) from accumulation (observables → conclusion).
- **ECBD** (ACL 2024): ECD applied to evaluating AI systems (NLP benchmarks); five modules
  (capability, content, adaptation, assembly, evidence); diagnosis: the design decisions
  of an evaluation "rest on tacit, untested assumptions".
- The application **ECD → pedagogical quality of AI-generated content** does not exist in
  publication: this system occupies that intersection (the examinee is the generator; each content, a work
  product). Adopted as **ECD-lite** (ADR-0013): 4 pieces, without psychometric machinery.

Sources: ECBD — aclanthology.org/2024.acl-long.861 (arXiv 2406.08723) · Mislevy (CRESST/WestEd,
Implications of ECD) · e-ECD (Frontiers 2019).

## 3. Evals tooling: terminology and calibration

- **Terminology:** *dataset*, *score*, *LLM-as-judge*, *trace*, *golden dataset*, *annotation
  queue* are genuinely universal terms. **There is no standard** for "the one who judges":
  scorer (Braintrust/MLflow) · evaluator (LangSmith/Azure) · metric (DeepEval/Ragas) · grader
  (OpenAI) · assertion (promptfoo) — and all of them fuse the *what* with the *who* (our
  Criterion × Assessor separation is not ceded). *Experiment* is ambiguous: a unit in
  LangSmith/Braintrust/Phoenix, a **container** in MLflow. → Equivalence table in
  `../../GLOSSARY.md`.
- **Judge calibration (judge alignment):** label once with humans (~50 items before
  automating), iterate the judge against that set (kappa ≥ 0.60 as a typical threshold); sampled
  human verification at 5–10% with queues prioritized by low agreement; periodic re-sampling
  against drift. → basis of ADR-0015.
- **EvalGen / "Who Validates the Validators?"** (UIST 2024): the *catch-22* — it is by grading
  outputs that humans discover their own criteria. Human verification feeds the
  design (our loop B), it does not only control it.

Sources: langfuse.com/docs/evaluation/core-concepts · galileo.ai (calibrate LLM judge) ·
evidentlyai.com (align judge with human labels) · langchain.com/resources/llm-as-a-judge ·
braintrust.dev (HITL platforms) · arxiv 2404.12272 (EvalGen) · deepeval.com · qaskills.sh
(OpenAI evals vs promptfoo vs Ragas).
