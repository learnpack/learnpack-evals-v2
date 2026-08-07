# ADR-0001 — Open content metadata validated by schema

**Status:** superseded by [ADR-0017](0017-declared-surface-is-the-package.md) ·
**Date:** 2026-07 · **DDD context:** Content Registry / Orchestration

## Context
The metadata of a content item varies **by content type** (a LearnPack course, a future
video, an article… do not share fields) and **by evaluation campaign** (which metadata is
presented to or required from the evaluator depends on the task). The `lessonPlan` case — added and
then discarded when the scope of what the evaluator sees changed — showed that hardcoding fixed
fields in the domain is fragile and pollutes it with details that change.

## Decision
1. **Intrinsic content metadata = open, typed collection.**
   `ContentMetadata` = set of `MetadataEntry {key, value, valueType}`. **No** struct of fixed
   fields. The domain never references concrete keys (`objectives`, `audience`, …).
2. **Validation via `MetadataSchema` (reference data).** A `MetadataSchema` tied to the
   `GeneratingSystem`/type declares allowed/required keys and types. It is config/data, not code.
3. **Per-campaign view/requirements.** `EvaluationCampaign.metadataView` defines which keys are
   presented/required to the evaluator. The "per campaign" variability lives here, not in the content.
4. **Ingestion via ACL.** An ACL at the edge of Content Registry translates the raw fields of the
   external system (LearnPack) into `MetadataEntry`.
5. **Presentation in adapters/UI.** How it is rendered (iframe/link, ordering, labels) is not domain.

## Consequences
- (+) Clean, extensible domain: new content types or campaigns require **config, not
  code**. No `if metadata.X`.
- (+) Separates the intrinsic (content) from the extrinsic (campaign).
- (+) Avoids `lessonPlan`-style churn.
- (−) A bit more indirection than fixed fields; schema validation is needed.
- **MVP:** **one** schema is seeded, `learnpack-v1 = {learningObjectives, targetAudience,
  prerequisites}`; the v1 campaign presents everything. The abstraction is open but the instance is one.

## Alternatives considered
- **Struct of fixed fields** (`objectives`, `audience`, `lessonPlan`…) → rejected: it pollutes and
  is rigid (as `lessonPlan` demonstrated).
- **Fully free bag without schema** → rejected: it loses meaning and validation (anemic).
- **Polymorphic subclasses per content type** → heavier; open collection + schema
  covers the case with less ceremony.
