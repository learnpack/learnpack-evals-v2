# ADR-0024 — The generator link is declared, never defaulted; and attributable later, once

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

`contents.generator_version_id` is nullable, and null means `unknown`: content valid for
per-content judgments, excluded from generator-level accumulation. That is a sound state — but
today it is also the **default**. Registering a content without mentioning a generator succeeds
silently, and the system whose purpose is generator QA loses, without a word, the very key it
accumulates by.

Block 7 turned the cost from theoretical into permanent and visible: an unknown content is
excluded from generator-level accumulation in **every** study report and named in the
`unknownExclusions` caveat. And there was no way back — no command, no endpoint, no repository
method writes `contents` after the INSERT, so `unknown` was forever.

Two facts shape the decision:

1. **`unknown` is sometimes the truth.** A human-written control course has no generator; so does
   third-party content registered for comparison. Making the link hard-mandatory would make those
   evaluands unregistrable, and would push whoever registers into inventing a value. An invented
   attribution is **worse** than an honest unknown: unknown is caveated in every report, a wrong
   generator is invisible and silently contaminates the accumulation of a generator that never
   produced that content.
2. **The link is a discovery, not a declaration that changes.** Which generator produced a course
   is a fact about the past; you record it when you learn it. Some packages will declare it in a
   future format, someone may recognize the course, an operator may find the record. What was
   never legitimate is *changing* an attribution already made.

## Decision

**The generator link is declared at registration — `unknown` remains legal, silence does not —
and an unattributed content can be attributed later, exactly once.**

1. **Declared, not defaulted.** `RegisterContentVersionCommand` and the HTTP request model lose
   the field's default: the caller must state a generator version or state `unknown`. The rule is
   ADR-0020's, one level up: *"nullable is not optionality: the field must be present and may be
   null. Silence is never evidence."* What this buys is honest to name: **key-presence, not
   thoughtfulness**. It cannot make a declaration sincere; it removes the case where nobody
   declared anything at all.
2. **Enforced at exactly two gates**: the HTTP request model and the application command.
   `EducationalContent` keeps its nullable field with its default — the entity records *state*,
   and it is reconstituted from rows with every field passed explicitly. There is no third gate,
   and `RegisterContentVersion` is the only writer of `contents`.
3. **The declaration belongs to whoever owns the payload's shape.** For our canonical bulk JSON
   the per-entry key is required. For the LearnPack ACL — whose shape has no generator concept —
   the declaration is a required flag of the import command, applying to the whole file, resolved
   once before the loop. There is deliberately **no fallback between the two**: a rule of
   precedence is where silence hides again.
4. **Attribution is a separate act, one-way.** `AttributeGenerator(contentId, generatorVersionId,
   attributedBy)` fills an unknown link and records who and when
   (`generator_attributed_by`, `generator_attributed_at`). It refuses a content that already has
   a generator: `unknown → known` yes, `known → other known` never. Filling a declared void
   records a finding; replacing an attribution would rewrite what was declared.
5. **The rule is stated in the domain and enforced in the database.** The aggregate raises when
   a generator is already known; the UPDATE carries `WHERE generator_version_id IS NULL`. They
   are not redundant: the first states the rule where it is read, the second holds it under
   concurrency.
6. **The provenance pair distinguishes a discovery from an original declaration.** Without it a
   non-null generator would be ambiguous between "the registrar knew it" and "someone
   reconstructed it later" — and since a wrong attribution is exactly the failure mode clause 1
   exists to avoid, the higher-risk of the two must stay distinguishable in the store forever.
   `_at` is also what lets anyone reconcile a frozen published report against current state.
7. The FK from `contents.generator_version_id` to `generator_versions.id` already guarantees
   integrity. The use case's own check exists to answer with a **422 naming the generator**
   instead of a constraint violation — ergonomics, not integrity. It is not redundant with the FK.
8. `edit_provenance` is orthogonal: `human_edited` content is still attributable to the generator
   that produced the first draft.

## Consequences

- (+) The accidental loss disappears at its source: no registration path — form, API, canonical
  bulk import, ACL import — can now omit the declaration.
- (+) `unknown` stops being a hole and becomes a **statement**, which is what makes filling it
  later legitimate rather than a correction.
- (+) A late attribution changes the report of an **open, not-yet-published** study: the report is
  composed at publish and reads the registry live, while the dataset was fixed at open. That is
  better truth at publication time and is left deliberately unguarded — the dataset's membership
  is what `OpenStudy` froze, not the evaluands' identity.
- (−) A **published** report's `unknownExclusions` keeps naming a content that has since been
  attributed. Published reports are immutable and must stay so (12-define inv. 3); this is
  precisely what `generator_attributed_at` is for — the reader can tell the report predates the
  attribution.
- (−) Every registration call site must now say something, including the ones whose subject has
  nothing to do with generators (test fixtures, seeds). In tests the declaration is written once
  per helper, where it is visible, and one test deliberately bypasses the helpers to protect the
  rule itself.
- (−) The bulk `--acl` path gains a required flag: an externally visible contract change for
  anyone scripting it.
- The `unknownExclusions` note in study reports is reworded — the exclusion is now a declared
  state and a repairable one. Reports published before this change keep their old wording, frozen.
- GLOSSARY's `ContentVersion` and `GeneratorVersion` entries are completed: they said `unknown`
  was allowed, which stays true; they did not say it must be declared, nor that it can be filled.

## Alternatives considered

- **Hard-mandatory generator at registration** → rejected: it makes legitimately ungenerated
  evaluands (a human-written baseline, third-party content) unregistrable, and buys false
  attributions from whoever must put *something* — the one failure mode no caveat catches.
- **A `Known(uuid) | Unknown` sentinel value object** instead of a required nullable field →
  rejected for now: it removes the type-level ambiguity of `None` and is the first thing a
  reviewer will propose, but it adds a translation at three boundaries for a distinction the
  required key already forces the caller to make. Revisit if `None` ever means a third thing.
- **A required reason for `unknown`** (`human_authored | third_party | not_recorded`) → rejected
  for this increment: it would let reports distinguish an intentional absence from a process
  failure, in the spirit of ADR-0018's "three causes, three remedies". Deferred deliberately, not
  by omission; the declaration comes first, the taxonomy when demand appears.
- **A separate `content_generator_attributions` table** → rejected: five readers ask
  `generator_version_id IS NULL` and the column is FK-backed; a side table would split the truth
  about one field across two places and force every reader to join for the same answer.
- **Deriving provenance from the `GeneratorAttributed` outbox row** instead of the two columns →
  rejected: the outbox is a delivery mechanism, not queryable history — the rows are consumed and
  deleted, and nothing else in the system queries them for state.
- **A general `update()` on the content repository** → rejected: the act needs exactly one narrow
  transition; a general mutator would open every other field to silent edits.

## Relationship with ADR-0022

ADR-0022 rejected **manual pairing** (an admin linking contents to briefs) as the *primary
channel*, because coordination does not scale and erodes silently. This ADR's attribution act is
not that: the primary channel remains the declaration at registration, and attribution is a
**repair** for the residue, one-way and with its actor recorded. The distinction is which one the
system relies on to be correct by default.

## References

ADR-0020 (§"nullable is not optionality — silence is never evidence", the rule this applies one
level up) · ADR-0017 (the declared surface is the package; no side channel — and the precedent
that discipline depending on institutional memory is not discipline) · ADR-0022 (mechanical brief
intake; the rejected manual pairing this act is distinguished from) · ADR-0019 (ratification: an
explicit act, recorded, that does not change identity — the shape this act follows) · ADR-0011
(coverage and denominators: what the exclusion of an unknown generator costs) · 13-code §3.6 and
§3.7 (the study report's generator level and its `unknownExclusions` caveat — the consumer that
makes the loss visible) · 12-define §Registry and 13-code §2 (frozen snapshots this ADR amends:
they describe `generator_version_id` as simply nullable) · GLOSSARY (`ContentVersion`,
`GeneratorVersion`) · STATUS 2026-08-07 (the decided-pending item this ADR resolves, including
"`unknown` is forever", now false).
