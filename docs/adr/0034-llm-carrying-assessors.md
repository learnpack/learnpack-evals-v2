# ADR-0034 — LLM-carrying assessors: semantics are identity, transport is environment

**Status:** accepted · §4 superseded by ADR-0037 · **Date:** 2026-08 · **DDD context:**
Pedagogical Evaluation · Evaluation Design · Identity

## Context

ADR-0016 made the automated assessor a versioned software artifact whose per-criterion
mechanism — "how much LLM it uses" — is internal detail, and declared that any change to
code, mapping, model, prompt or internal threshold is a new version and therefore a new
identity. The first assessors (`structural`, `drafts-structural`) never had to exercise the
LLM half of that sentence: they are pure code over checked profiles. Building the first
LLM-carrying assessor forces four questions the earlier artifacts never asked.

1. **Where does the identity of an LLM call end?** A call has semantic parts (which model,
   which prompt, which output schema, which temperature, what the retry feedback says, how
   the answer is turned into pass/fail) and plumbing parts (which HTTP client, how 429s are
   backed off, what the timeout is, which base URL routes the request, which key
   authenticates it). Reading ADR-0016 maximally — *everything* in the path is identity —
   would mean a timeout tweak re-versions every LLM-carrying assessor at once, which is the
   exact spurious-invalidation failure ADR-0016 rejected the shared check library for.
   Reading it minimally would let a model swap hide inside an environment variable, and a
   swapped model silently keeps a calibration that was never its own.

2. **Where does the model name live?** The obvious ergonomic answer — an env var, so
   "changing the model is a config change" — is wrong on ADR-0016's own terms: two runs of
   the same assessor version under different models are two different judges wearing one
   identity, and every downstream comparison (repetitions, dispersion, fitness under equal
   coverage, ADR-0023 §7) silently breaks.

3. **What happens when the model fails for real?** Retries can absorb transient transport
   errors and schema violations, but a budget eventually runs out. Executors produce only
   `pass`/`fail`; every non-scored outcome is derived mechanically before the executor runs
   (ADR-0016, `derivation.py`). There is no honest scored answer for "the judge could not
   judge", and inventing a runtime outcome for it would put a non-scored state in the
   assessor's hands — the invariant ADR-0018 exists to keep out of them.

4. **What may be shared between assessors?** ADR-0016 allows bottom-up shared utilities
   "with the discipline of bumping the version when touching them". Taken literally for an
   HTTP client, that discipline re-creates the shared-library invalidation problem: a
   backoff fix would demand bumping every LLM-carrying assessor, so either the fix is not
   made or the versions become noise.

## Decision

**The semantic surface of an LLM call is assessor identity and lives pinned in the
assessor's code; the transport under it is environment, shared in `app/platform/`, and
changing transport re-versions nothing.**

1. **Identity (in the assessor package, declared in `SOURCE_CONFIG`):** the model id per
   task, the provider namespace it implies, the prompts, the output schemas, the sampling
   parameters (temperature, and any future top-p/seed), the wording of the
   schema-violation feedback, the grounding rules, and every constant that turns extracted
   or classified data into a scored outcome. Changing any of these is a new assessor
   version — calibration does not transfer, exactly as ADR-0016 already governs.
   `SOURCE_CONFIG` carries the per-task model ids and a **fingerprint (hash) of the prompt
   texts**, computed from the code at import: the existing ratification guard, which
   refuses a stored `source_config` that differs from the code, thereby catches a prompt
   edited without a version bump.

2. **The model id is pinned in code, never read from the environment.** "Easy to change
   the model" is honored the cheap way the system already owns: edit one constant, bump
   `VERSION`, re-ratify. Different models for different tasks are different constants in
   the same artifact. What the environment supplies is access, not identity: the API key
   and the base URL.

3. **Transport is a platform concern** (`app/platform/llm.py`): an OpenAI-compatible
   chat-completions client over `httpx`, with retry/backoff for transient transport
   failures and typed errors. It is deliberately provider-agnostic plumbing — OpenRouter
   today, any endpoint speaking the same wire format tomorrow — and touching it does not
   re-version any assessor, for the same reason upgrading `httpx` never did. The line is
   testable: a transport change may alter *whether and when* an answer arrives, never
   *which* answer arrives.

4. **An irrecoverable LLM failure aborts the whole evaluation; nothing persists.**
   Transient transport errors are retried with backoff; a schema violation or an
   ungrounded quote is retried with the validator's feedback; when the budget is spent,
   the executor raises a typed error and the evaluation ends with no evaluation row, no
   event, no judgment — the same all-or-nothing shape the extraction path already has
   (`ExtractionError` → a `failed` profile, never a half-profile). Retrying is running
   `evaluate` again. Executors keep producing only `pass`/`fail`; the derivation's
   invariant is untouched.

5. **Everything semantic is duplicated per assessor, on purpose.** Prompts, schemas, the
   structured-output-with-feedback loop, grounding checks, decision constants: copied into
   each LLM-carrying assessor like `drafts-structural` copied `structural`'s executors.
   The industry patterns keep their industry names inside the package (it is
   infrastructure — the ACL side of the GLOSSARY's equivalence table), so the recurring
   shapes stay recognizable across assessors even though the code is deliberately not
   shared.

## Consequences

- (+) A prompt, model or threshold change cannot silently keep a calibration: it either
  bumps the version or is refused at ratification by the fingerprint guard.
- (+) Transport fixes (backoff, timeouts, connection reuse) land once, in one file, and
  invalidate nobody — the spurious-invalidation cascade is structurally closed.
- (+) Provider mobility is an environment change only when the wire format holds
  (base URL + key); when it does not, the platform client is the single thing to swap.
  Moving a *task* to another provider's model is an identity change, as it should be:
  the model id's namespace names the provider.
- (+) Cost and latency are observable per evaluation without new machinery: the tasks
  report tokens, latency and attempts as `ComputedMetric`s that travel with the
  evaluation.
- (−) A model deprecated by the provider bricks the assessor version until a new version
  pins a successor — deliberate: the successor is a different judge and must not inherit
  the calibration.
- (−) Aborting whole evaluations makes long batch runs sensitive to one flaky criterion.
  Accepted for now: evaluations are cheap to re-run, and a partial evaluation would be a
  lie in the store. If batch pressure arrives, the answer is resumable *batching around*
  evaluations, not partial evaluations.
- (−) Duplicated semantics mean a genuinely better retry-feedback wording must be copied
  by hand into other assessors, each with its own version bump. That is ADR-0016's cost,
  accepted knowingly: those bumps are real identity changes.

## Alternatives considered

- **LiteLLM (or the OpenAI SDK) as the client** → rejected for now: OpenRouter is already
  a multi-provider router behind one OpenAI-compatible surface, so a second router adds a
  fast-moving dependency without adding mobility; the SDK saves little over `httpx`
  (already a dependency) while splitting retry semantics between two layers.
  Reconsideration trigger: needing a provider that does not speak the OpenAI wire format.
- **Model id from an env var** → rejected: it makes the cheapest identity change
  invisible to the identity system (see Context 2).
- **A runtime "could not judge" outcome** → rejected: it hands a non-scored state to the
  assessor at runtime, breaking the ADR-0018 invariant, and it would leak into every
  consumer (fitness denominators, coverage, reports) for what is operationally a retry.
- **Persisting the partial evaluation** → rejected: coverage is exact by construction
  (one outcome per criterion of the snapshot); a partial row would need a new state to
  say "incomplete", which is the previous alternative in disguise.
- **Sharing the semantic helpers as a library with version-bump discipline** → rejected:
  ADR-0016 names the discipline, but a helper edit that re-versions N assessors at once
  is indistinguishable from the shared check library it already rejected. Duplication
  keeps each artifact's blast radius its own.

## References

ADR-0016 (the assessor as versioned artifact; identity through version; the shared-library
rejection this ADR extends to the LLM path) · ADR-0018/ADR-0019 (declared coverage;
non-scored outcomes derived mechanically, never decided at runtime) · ADR-0009 (verbatim
quotes as evidence — the grounding rule's ancestor) · ADR-0023 §7 (equal-coverage
comparability, what an env-var model would silently break) · `content_profiling`'s
`ExtractionError` → `failed` profile (the all-or-nothing precedent) · the *judge drift* /
"version your judge" literature the GLOSSARY's equivalence table cites.
