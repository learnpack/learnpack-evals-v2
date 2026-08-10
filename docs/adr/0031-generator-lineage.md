# ADR-0031 — A generator is an entity; its versions belong to it

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

`GeneratorVersion {id, name, version, metadata}` is the declared identity of the examinee, and the
key everything generator-level accumulates by (ADR-0013). Its integrity rests on
`UNIQUE(name, version)` plus an `exists(name, version)` check in the use case — and on `name`
being free text, retyped by hand at every version registration. `POST /admin/generators` is the
only gate that mints one.

So the lineage — *which generator this is a version of* — exists nowhere in the model. It is a
string repeated correctly, registration after registration, by whoever is at the keyboard. When
that repetition fails, the system does not notice: `learnpack-genertor 2.4.0` is a perfectly valid
new identity, and what was meant as the next version of a generator is recorded as the first
version of a different one.

**A unique constraint cannot catch this, by construction.** Uniqueness protects against
*collision* — two records turning out to be the same thing. The failure here is the opposite one,
an unwanted *distinction*, and no constraint can tell a typo from a name nobody has used before.
Tightening the constraint narrows the surface (casing, stray whitespace) and leaves the failure
itself untouched.

Two facts make the cost worse than the frequency suggests:

1. **It is permanent.** `GeneratorVersion` is immutable and `RegisterGeneratorVersion` is its only
   writer (ADR-0030 §3). Nothing renames, nothing merges, and `contents.generator_version_id`
   points at the phantom from then on. If a study publishes before anyone notices, the wrong name
   is frozen inside `study_reports.report`, which is immutable by design (12-define inv. 3).
2. **The volume arrives exactly where the guard is weakest.** The genetic-algorithm experiment
   (ADR-0023) registers many versions of the same generator in sequence. Every one of them retypes
   the name; the exposure scales linearly with the number of individuals, in the one workflow this
   whole context exists to serve.

This is the same defect class ADR-0017 named and ADR-0024 acted on: *discipline that depends on
institutional memory is not discipline*. ADR-0024 removed the accidental null by making the
generator link a declaration and forbidding silence. It did not touch the layer below — what the
declaration points **at** — because there was nothing there to point at but a string.

## Decision

**The lineage becomes an entity. A `Generator` owns its `GeneratorVersion`s, the name is typed
once per generator instead of once per version, and the one gate where a name is still typed is
guarded.**

1. **The lineage is a row, not a repeated string.** `Generator {id, name}` is new;
   `GeneratorVersion` becomes `{id, generatorId, version, metadata}` and loses its `name`.
   Registering a version is selecting a parent by id and declaring a version string — the act no
   longer has a name to misspell. The lineage was always in the model; it was spelled as a
   convention and is now spelled as a foreign key.
2. **The lineage declares nothing but its name.** No metadata blob, no config, no description.
   Reference data a version declares about itself stays on the version, where ADR-0030 §2 put it.
   The reason for the emptiness is not minimalism: a blob on the lineage is precisely where
   someone would put back the generator internals ADR-0030 §1 removed from this system, and a
   place that exists gets filled.
3. **Two acts, of very different frequency and authority.** Minting a lineage
   (`POST /admin/generators`, `register-generator`) is rare and deliberate. Registering a version
   under it (`POST /admin/generators/{generatorId}/versions`, `register-generator-version`) is
   routine and, in the genetic-algorithm loop, scripted. They are not folded into one
   find-or-create verb: that would re-open the name-typing gate at every version registration,
   which is the defect itself, and it would hide two acts of different authority behind one word.
   `GET /admin/generators` therefore returns lineages, and versions move to
   `GET /admin/generator-versions` — a resource does not get to mean two things.
4. **The remaining name-typing gate is guarded by near-miss refusal, and the override is an
   echo.** Minting a lineage whose name is within a small edit distance of a registered one is
   refused, naming the candidate. It proceeds only when the caller repeats that candidate back
   (`confirmDistinctFrom`), which is what makes the override evidence that a human read the
   specific name rather than a flag a script carries by default. An exact match on the normalized
   key is refused outright and cannot be overridden — that is not a near miss, it is the same
   lineage.
5. **The rule is stated in the domain and held in the database.** Normalization
   (case and surrounding whitespace) and the distance rule are pure domain functions; the store
   carries a unique expression index on the same normalization, a foreign key from version to
   lineage, and `UNIQUE(generatorId, version)`. This is ADR-0024 §5's shape: the first states the
   rule where it is read, the second holds it under concurrency. The database is not asked to
   judge similarity — it cannot, and the judgement is the operator's.
6. **What this buys, stated weakly, because the strong version is false.** The typo becomes
   *unrepresentable* at version registration. At lineage registration it stays as representable as
   ever; the guard only makes it *likely to be caught*. Said the other way round: the guard is what
   fixes the defect, and the entity is what keeps the guard credible — fired once per lineage it is
   a rare, high-attention refusal, whereas fired at every version registration it would be constant
   noise in a population whose names are deliberately similar, and it would decay into a keystroke.
   Neither half is redundant, and the weak claim is the one to defend later.
7. **The individual of the genetic algorithm is still the `GeneratorVersion`.** An individual is a
   configuration that can be *run*, and a lineage cannot be run. What the lineage adds is the grain
   at which individuals are grouped across generations — a question that previously had to be
   answered by matching strings.
8. **No sub-component axis is created, and no convention changes.** ADR-0030 §4 refused an axis
   that would version *parts of* a generator; a lineage groups *whole versions*, and the version
   ends up with fewer writable fields than before, not more. ADR-0027 §5's
   `courses/<name>@<version>/` convention is untouched on disk: only its resolution becomes two
   steps, inside the one function that ADR-0027 declared provisional and named "richer
   generator-folder conventions" as a door for.

**Deferred, doors left open:** `rename-generator` — now thinkable, since the name lives in one row
and is no longer part of any version's declared identity, but not built (see below); a read model
on the query port, if the two reads the DTO join now ever cost anything; and version strings minted
by the genetic-algorithm loop rather than declared, which would take the last hand-typed field out
of the routine act.

**Why `rename-generator` is deferred rather than built.** `study_reports.report` and the fitness
projection embed the generator's name at publish time, and a published report is immutable. A
rename would therefore correct the console and leave the typo permanent in every report already
published — a subtler and more confusing state than the one it replaces, for a defect the guard
makes rare and catches *before* any report exists. When the demand appears it takes ADR-0024's
shape: one-way, actor and time recorded, refusing what is already declared, offered at the two
gates. This is the same move ADR-0030 §3 made for the metadata correction.

## Consequences

- (+) The failure this ADR exists for disappears from the routine act entirely: no registration
  path — API, CLI, seeder, `courses/` tree — types a generator name when registering a version.
- (+) Generator-level analysis gains a grain it did not have. "Every version of this generator"
  is a foreign key instead of a string match, which is what the genetic algorithm compares
  generations over.
- (+) The read side does not move. The version DTO keeps `name`, joined from its lineage, so
  `GeneratorInfo`, the study report JSON, the fitness JSON and every screen that renders
  `{name} {version}` are unchanged — the split is confined to the write side.
- (+) A misspelt lineage is now correctable *in principle* (one row, no longer part of a version's
  declared identity), where before it was permanent by construction. The act is deferred, but the
  door exists, which it did not.
- (+) The CLI gains the two acts it never had. Registering a generator was HTTP-only or the
  seeder's business, which STATUS carried as a production prerequisite with no command behind it.
- (−) `GET /admin/generators` changes shape: it returned versions and now returns lineages. A real
  breaking change, accepted because the deploy is pending and the only client is this repo's
  console — and because leaving it would make the resource mean one thing to POST and another to
  GET.
- (−) Two acts where operators knew one. Registering a generator version now requires that the
  lineage exist first, and a first-time registration is two calls instead of one.
- (−) The near-miss threshold is a judgement with no data behind it. If `confirmDistinctFrom`
  starts appearing in every script the guard has failed and the constant needs revisiting; that is
  the trigger to watch, and it is named here rather than discovered later.
- (−) Two reads where there was one: the version DTO joins its lineage name in Python rather than
  in SQL, because the repository ports in this context return domain objects without exception.
  Bounded, not free — the escape is named above.
- (−) The migration folds pre-existing names that differ only in casing or surrounding whitespace
  into one lineage, keeping the earliest-declared spelling. Two rows could differ that way because
  `name` is plain text and the old unique constraint compared byte for byte. The folding is
  deliberate, and the discarded spelling stops being queryable state — it survives only as the
  `name` inside the `GeneratorVersionRegistered` row of the append-only outbox, which is a past
  fact and not something anything reads. Where the fold would instead collide on
  `(generatorId, version)`, the migration refuses rather than choose which registration was the
  real one.
- (−) `docs/design/12` and `13` keep describing `GeneratorVersion` as `{id, name, version}`. They
  are frozen snapshots and are not corrected; this ADR is what supersedes them.

## Alternatives considered

- **Keep the flat shape; add a normalized unique index and the near-miss guard to
  `RegisterGeneratorVersion`** → rejected, and it is the strongest alternative: it catches the same
  typos for a fraction of the cost, with no new entity, no endpoints and no test churn. It breaks
  on frequency. Under the flat shape the guard has to fire at *every version registration*, and a
  genetic-algorithm population is built out of deliberately similar names — so the guard fires
  constantly, the override becomes reflexive, and within a week it is a flag every script carries.
  A guard that is always on is a guard that is never read.
- **One find-or-create endpoint taking `{name, version}`** → rejected: it keeps every call site and
  every test untouched, and it keeps the free-text name at the routine gate, which is the defect.
  It also gives one verb to two acts whose frequency differs by orders of magnitude.
- **A boolean override (`confirmNewGenerator: true` / `--force-new`)** → rejected in favour of the
  echo: a blind retry passes a boolean, and a script can carry it permanently. Echoing the
  candidate costs one string and cannot be set in advance, because its value is the server's answer.
- **An edit-distance threshold scaled by name length** → rejected: the real typo classes
  (transposition, doubled letter, dropped letter, wrong separator, wrong case) are within two edits
  regardless of length, and a scaled rule cannot be explained inside the refusal message. A flat
  threshold with a floor for very short names says the same thing in one sentence.
- **A `CHECK` constraining the name's charset (a slug rule)** → rejected: it is a guess about the
  vocabulary of a free-text label, which the domain's own promotion rule already refuses, and it
  would forbid `@` — a character that already carries meaning in the `courses/` folder convention.
  The two failure modes it would catch (blank, casing) are covered by a not-blank check and the
  normalized unique index.
- **A stored `name_key` column instead of a unique expression index** → rejected: a second column
  holding a function of the first has to be kept true by every writer, and the expression index
  makes the database compute what the domain defines.
- **Building `rename-generator` now** → deferred, not rejected: see the Decision. The reason is the
  frozen published report, not the effort.
- **Letting the `courses/` intake mint a lineage when the folder names an unknown one** → rejected
  by ADR-0027's own rule: mechanical intake never mints generator identities, and a convention that
  creates them is silence wearing a convention.

## References

ADR-0030 (§1 the generator's internals stay outside — why the lineage carries no blob; §3
write-once, the stance the deferred rename follows; §4 no sub-component axis, which clause 8
distinguishes) · ADR-0027 (§5 the `courses/<name>@<version>` convention, declared provisional and
isolated in one resolution function, with "richer generator-folder conventions" as a stated door;
and its rule that mechanical intake never mints generator identities) · ADR-0024 (the declaration
that removed the accidental null one level up; §5's "stated in the domain, enforced in the
database"; and the one-way repair shape the deferred rename would take) · ADR-0023 (the fitness
projection: the genetic-algorithm loop whose volume makes this failure likely, and the frozen
generator name it publishes) · ADR-0017 (the declared surface is the package — and the precedent
that discipline depending on institutional memory is not discipline) · ADR-0013
(`GeneratorVersion` as the accumulation key of generator-level claims — the phrase that already
presupposed a generator) · ADR-0006 (query ports and Python aggregation, the shape the joined
version DTO follows) · amends the `GeneratorVersion` shape in `docs/design/12-define-qa.md`
§*Registry* and `13-code-qa.md` §3.2 · GLOSSARY (`Generator`, `GeneratorVersion`, `Fitness`) ·
`docs/DATA_MODEL.md` · `courses/README.md`.
