# ADR-0030 — The generator declares reference data about itself, not artifacts

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

`GeneratorArtifact` entered the model as a generator-level counterpart to the package artifacts:
a `{kind, locator}` row hung off a `GeneratorVersion`, hand-typed in the admin console, under the
first-increment mark **"register yes, extract no"** (09-align §*Discoveries*, 12-define §*First
increment*, 13-code §1). The reasoning was diagnostic: when a study reports that a generator
regressed, the prompt template pinned to that version would explain why.

It was built and never used. Nothing subscribes to `GeneratorArtifactRegistered`; the only reader
of `generator_artifacts` is the list endpoint feeding the dialog that writes it. That alone would
argue for deletion on cost, but two stronger reasons make it a modelling error rather than an
unfinished feature.

**It sits on the wrong side of the boundary this context already drew.** The `GeneratorVersion`
docstring states that the identity is *declarative and unverifiable from inside the system — the
generator lives outside*. A generator is a multi-step workflow; attributing a regression to one of
its steps is work for the team that owns those steps, in their own versioning and changelogs. A
copy of a single prompt template held here would be perpetually partial and silently stale, while
carrying the authority of a registered fact.

**It contradicts the finding of ADR-0027.** That ADR established that hand-typed `{kind, locator}`
rows leave the `kind` vocabulary without an owner and the data unverified, and removed them from
content registration in favour of mechanical discovery. It scoped itself to the package axis, but
the generator form is the same anti-pattern — an open `kind` typed by a human, that nothing
validates and nothing reads. Discovery is not available as the fix here: there is no package to
enumerate, because the artefacts in question live in a repository this system has no access to.

A related error is live in code. `seed-demo` registers the demo generator with
`metadata={"promptPreprocessor": "not versioned yet"}`, and the surrounding notes read as if the
prompt preprocessor were a component to be versioned inside `metadata`. It is not: it is step 1 of
the generator's workflow. Changing it changes the generator, which the model already answers —
*different config ⇒ different examinee ⇒ claims do not transfer*.

What the team does want is smaller than what was built: an optional, human-readable note about
what changed in a version, read alongside the results. `GeneratorVersion.metadata` already carries
it end to end — request, use case, `jsonb` column, response — and only the admin form failed to
offer it.

## Decision

**The generator's internals stay with the generator. What a version may declare about itself is
optional reference data, in its identity blob.**

1. **`GeneratorArtifact` is retired in full** — entity, table, event, use case, endpoints and UI.
   This system does not custody the generator's prompts, workflow steps or configuration; those
   live with the generator's own code and changelog, where they can be kept true.
   **Scope, precisely:** this clause is about the *generator's insides*. It does not touch
   generator-**produced** data, which is evidence and stays exactly as it is — the package
   artifacts of ADR-0017, discovered by ADR-0027, and the `GenerationBrief` of ADR-0022.
2. **Optional reference data goes in `GeneratorVersion.metadata`.** Free-form, following the rule
   the domain already states: a key is promoted to a typed column when something consumes it, not
   before. The only key intended today is `changelog` — prose, for a human reading a report. The
   blob stays open because the demand is exploratory: a future evaluating system may want to
   record something else about a version, and guessing its shape now is exactly the promotion the
   rule forbids.
3. **The declaration is part of the identity, and therefore write-once.** `GeneratorVersion`
   remains immutable and gains no update path. A narrow one-way act to correct a typo would take
   the shape of ADR-0024's `attribute-generator` — actor and time recorded, refusing what is
   already declared — and is **deferred** until someone needs it. Until then, a wrong note is
   corrected by registering another version.
4. **A change in any step of the generator's workflow is a new `GeneratorVersion`.** There is no
   sub-component versioning axis, and `metadata` is not one: it annotates a version, it does not
   version anything. This retires the `promptPreprocessor` idea, in the seeder and in the notes.

**Deferred, doors left open:** the update act of clause 3; and the promotion of `changelog` to a
typed column, when it proves to be always present and always read.

## Consequences

- (+) Deletes a write-only entity — table, event, two endpoints, a repository, a port, a DTO, a
  use case and a form — and with it a `kind` vocabulary nobody owned.
- (+) The console stops offering an act with no consequence. Filling that form changed nothing
  observable anywhere in the system, which is the worst thing an admin screen can do.
- (+) The repo stops arguing both sides of ADR-0027: hand-typed artifact rows are now gone from
  both axes, for the same stated reason.
- (+) The changelog costs no schema and no migration — the column, the request field and the
  response field already exist. Only the form and a read-only dialog are new.
- (−) The diagnostic intent is genuinely dropped, not relocated. When a study shows a regression,
  this system will hold a prose note and nothing machine-readable about what changed. That is
  accepted: the honest version of that data is not ours to hold.
- (−) A free-form blob invites key drift — one registration writes `changelog`, another `notes`.
  Mitigated only by the form writing a single key; anything arriving through the API is
  unconstrained by design.
- (−) A typo in a changelog is uncorrectable without a new generator version (clause 3). Accepted
  while the demand is hypothetical; the exit is named.
- (−) `docs/design/09`, `12` and `13` keep describing `GeneratorArtifact`. They are frozen
  snapshots and are not corrected; this ADR is what supersedes them.

## Alternatives considered

- **Keep the entity and build a consumer** (an assessor or report that reads the prompt template)
  → rejected: it would make the fitness track a copy of the generator's insides that we cannot
  verify or refresh, and ADR-0023 §*rationale* already refuses signals that measure our tooling
  instead of the artifact.
- **Keep the table, delete only the UI** → rejected: the worst of both. The concept survives with
  no owner, no reader and no way to inspect it — a schema that exists to avoid making a decision.
- **Add a typed `description`/`changelog` column instead of using `metadata`** → rejected for now
  by the domain's own promotion rule (clause 2). The stated demand is exploratory, which is
  precisely when a blob is correct and a column is a guess. Promotion stays available and is
  purely additive.
- **Make the changelog editable after registration** → rejected as the default: it is declared as
  part of the identity (clause 3), and an editable field on an immutable aggregate needs its own
  act with actor and time, which ADR-0024 already shaped. Deferred, not refused.
- **Ask LearnPack to ship the original prompt inside the package, and drop the generator axis
  entirely** → rejected as a *justification* for this decision. It is a change to the package
  format — a future `LearnpackV2` — so it says nothing about the courses being evaluated today,
  and it depends on a third party. It remains a live forward ask under ADR-0022, unaffected
  either way.

## References

ADR-0027 (hand-typed `{kind, locator}` rows: the finding this extends to the generator axis) ·
ADR-0024 (the shape the deferred update act of clause 3 would take; the one-way declaration
pattern) · ADR-0022 (the `GenerationBrief` and its forward ask — generator-*produced* data,
untouched) · ADR-0017 (the declared surface is the package — also untouched) · ADR-0013
(`GeneratorVersion` as the accumulation key of generator-level claims) · amends the
`GeneratorArtifact` marks in `docs/design/09-align-discover-qa.md`, `12-define-qa.md` §*First
increment* and `13-code-qa.md` §1, §3.2 and §8 · GLOSSARY (`GeneratorVersion`) ·
`docs/DATA_MODEL.md`.
