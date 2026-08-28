# ADR-0058 — A dataset is a named set, and changing it is a new version

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Datasets (new) ·
Evaluation Orchestration · Evaluation Studies · Golden Dataset

## Context

A campaign's scope is chosen inside the act that opens it: `OpenCampaignCommand` takes
`content_ids`, the ids land in `campaign_contents`, and that is the end of them. The set has no
name, cannot be reused, and cannot be pointed at twice. Opening the second campaign over the
same forty courses means ticking forty checkboxes again, and nothing in the store knows the two
sets are the same one.

**What is missing is not reproducibility.** ADR-0002 already fixed the scope at open and
nothing can edit it afterwards, so what a past campaign judged is already safe. What is missing
is **identity**: the ability to say *these two rounds ran on the same set*, or *on that set plus
eight courses*. That sentence is unsayable today, and it is the sentence a second round needs.

It is also what the correlation the human panel exists for depends on. ADR-0015 §4 correlates
each claim with the human score of its quality **across the contents of the set**, and the
measurement literature states the same requirement as a reporting rule: an instrument and the
criterion it is validated against must be applied to the same subjects, documented as such. The
campaign picks its courses by hand; a study composes its own by recipe (ADR-0044). Nothing
today can state the relationship between the two, so "the same courses" is checked by reading
two lists side by side.

**The industry converged on the shape and not on the trigger.** LangSmith, Langfuse, Braintrust
and Phoenix all separate a dataset from its versions, and all four mint a version *implicitly*,
on every mutation, identified by a timestamp or a transaction id. None of them has an explicit
act, and none of them records **why** a version exists. That trade is right for a set edited
continuously from a CRUD screen and wrong here: this set is curated deliberately, a few times a
year, and an implicit line would fill with anonymous entries whose reason nobody wrote down.
The pattern that fits is the one benchmarks use — `lm-evaluation-harness` bumps an integer only
on a change that breaks comparability, and requires a changelog line naming the defect.

Versioning is also unusually cheap here, for a reason worth recording: every tool that stores
the expected output *inside the item* needs per-item revision history to correct it. Ours does
not — the human reference supplies the expected output (ADR-0015), and members are ids of
contents that are immutable and never retired (ADR-0033). A version is a set of pointers.

## Decision

**A dataset is a named, reusable set of evaluands. Its membership is frozen in versions, a
version is created by an explicit act that must say why, and a membership that changes nothing
is not a version.**

### 1. Two levels, and the act creates both

A `Dataset` is the concept — what people call the set — and a `DatasetVersion` is a frozen
membership under it. Declaring a dataset mints its first version in the same act: a dataset
with no version is not a set, and the intermediate state would exist only to be left behind.

Versions are **immutable** and numbered per dataset from 1. There is no draft: editing a
membership means minting the next version, which keeps the line free of states a reader has to
interpret.

### 2. Only membership bumps. A label binds nothing

Renaming a dataset or changing its description mints no version, by ADR-0055's rule: the id
identifies, the name describes. A rename that renames nothing writes nothing and emits nothing.

### 3. The note is required

Every version carries a note saying why it exists, and a blank one is refused by the aggregate
and by a check constraint underneath it — one rule in the two places that can enforce it.

This is the clause that earns the explicit act. A version without a reason leaves the numbers
of every earlier round **invalid and uninterpretable at the same time**: a reader knows they
cannot be compared and cannot find out what changed. The note is what turns "those numbers are
stale" into "those numbers predate the eight courses from 2.0.0".

### 4. A membership equal to the current one is a no-op, not a version

Detected by `member_set_hash` — sha256 over the sorted, de-duplicated member ids — and refused
with a 409. Order and repetition are not part of what a set is, so neither reaches the digest.

This is the rule ADR-0050 and ADR-0054 already state in their own contexts: **a change is
recorded and a no-op is not**. Only the *current* version is compared: returning to an earlier
membership is a real change from where the set is now, and refusing it would refuse a true
statement about the set today.

The hash is stored, not recomputed on read, because it does a second job — it is a key that
outlives a local database, the property ADR-0039 §4 bought when it published `brief_hash`
*because the id is not portable*.

### 5. A campaign will point at a version **and** keep copying its members

When the campaign is bound to a version (the block after this one), the version records **how
the set was chosen** and the copy in `campaign_contents` remains **what was judged**. Two
mechanisms, one of them derived, and deliberately not one: the copy already exists, assignments
depend on it, and a second source of truth for the same set is a thing that can disagree with
itself.

This costs less than it does for the tools that copy rows because our members are pointers to
immutable contents; the reason to keep the copy is the assignment path, not the mutability.

### 6. A new scope is a new dataset; a correction is a bump

Adding or removing courses is a version. Changing what the set is *for* — another population,
another generator family — is a **new dataset with its own name**. This is the discipline the
benchmark community arrived at after correcting sets in place proved unrecoverable: SWE-bench
Verified, MMLU-Redux and MMLU-Pro are all named artefacts that coexist with the original rather
than replacing it, and a superseded release is retired and archived, never deleted.

### 7. Studies keep composing by recipe; only one direction is permitted

A hand-enumerated version **is not admissible as a study's dataset**. ADR-0044 §9 requires a
study's contents to be `briefs × generatorScope`, because pairing by commission is what makes
comparing generator versions an experiment rather than two samples; a hand-picked list carries
no pairing, no declared population for the report to read, and nothing repeatable when the next
generator version arrives.

The permitted direction is the inverse: **minting a version from the contents a study
materialized**, so the human panel can run over exactly what the instrument measured. The
recipe still originates the set, so the pairing is inherited rather than fabricated. Decided
here, **not built here**; when it is built, a derived version records what it came from, and an
edit afterwards makes the lineage *derived from*, never *equal to*.

### 8. Comparability is a gate, not a convention

When `CompareStudies` is built, the dataset version joins the instrument version in what it
validates. All four tools surveyed allow comparing runs across different versions of the same
dataset with no warning — verified in Phoenix's own resolver, which refuses different datasets
and permits different versions in silence. We already refuse to let two rounds be compared
across instrument versions, and already publish coverage because *"these numbers may be
compared" has to be checkable rather than assumed* (ADR-0023 §7). This is the same rule, on the
axis that had no gate.

### 9. The vocabulary: dataset, version, sample

Three names for three things that are today all called "the set":

- **dataset** — the reusable concept (this ADR),
- **dataset version** — the frozen membership (this ADR),
- **sample** — what a round *actually* measured.

The third is what the validity coefficient belongs to: not the version put in front of people
but the intersection that came back — the contents that reached human quorum **and** carry an
automated judgment. It is a **derived read, not an aggregate**: it is the outcome of two things
that already happened, and making it a stored thing would oblige something to keep it true.

`GoldenDataset` is unchanged. It remains the human reference per
`(contentSet, instrumentVersion)` and becomes one of the two inputs that read produces.

Renaming the study's `EvaluationDataset` value object to *sample* follows in its own block,
so that the rename and this feature are not one diff.

### 10. `[future]` — anchor courses

Comparing two campaigns whose memberships differ needs a common subset carried across versions
and evaluated in both: the linking-by-anchor-items design that keeps test forms interpretable
against a growing item bank. Named so it is not reinvented; not built, and not implied by
anything above.

## Consequences

- (+) The set becomes a thing with a name, reusable across campaigns, and the sentence "the
  same courses as last time" becomes checkable instead of asserted.
- (+) The version line carries its own reasons, so old results stay interpretable.
- (+) The no-op refusal keeps the ordinals meaningful: `v7` means the set moved seven times.
- (−) One more act before opening a campaign. The dataset must exist first, which is the point
  and is still a cost.
- (−) A dataset built by hand and a study's recipe remain two ways of composing a set. Clause 7
  contains the overlap; it does not remove it.
- (−) `member_set_hash` is a second identity for a version, alongside its id. Two identities
  for one row is a thing to keep honest — the id addresses, the hash compares.

## Alternatives considered

- **Implicit versioning on every mutation**, as all four eval platforms do. Rejected: it
  removes the act that clause 3 exists to attach a reason to, and produces a version line where
  most entries record that somebody pressed save.
- **No versions at all; an immutable set, and editing forks a new one.** Nearly equivalent in
  what it protects, and worse at what this is for: the lineage would live only in names, so
  "the same set plus eight courses" would be two unrelated datasets.
- **The version as the campaign's only record of its scope**, dropping `campaign_contents`.
  Rejected by clause 5: the assignment path reads that table, and a pointer whose target can be
  deleted has documented failure modes (Delta's VACUUM, W&B's TTL, Phoenix's cascade from a
  dataset to every experiment over it).
- **Content-addressed identity, the way MLflow makes a dataset's digest its identity.**
  Rejected as the *primary* key: identical membership for two different purposes is a real and
  useful thing to have (clause 6), and a digest cannot express a line. Kept for what it is good
  at — detecting the no-op (clause 4).
- **Making the sample an aggregate.** Rejected by clause 9: it is derived from facts that
  already exist, and storing it would create an obligation to keep it current.
- **A unique name per dataset.** Refuses a true statement and buys nothing: nothing looks a
  dataset up by name.

## References

ADR-0002 (the open campaign: what opening fixes) · ADR-0015 §4 (the correlation this set
serves) · ADR-0023 §7 (comparability has to be checkable, not assumed) · ADR-0027 / migration
0014 (`content_hash`: identity by contents, for dedupe and drift) · ADR-0033 (content is never
retired — why a member stays resolvable) · ADR-0039 §4 (the hash is published because the id is
not portable) · ADR-0043 (choosing is not pinning) · ADR-0044 §9 (a study's contents are
`briefs × scope`, never picked one by one) · ADR-0050 (an event says what changed, and a no-op
is not an event) · ADR-0054 (a change is recorded and a no-op is not) · ADR-0055 (a label binds
nothing) · GLOSSARY (`Dataset`, `DatasetVersion`, `EvaluationDataset`, `GoldenDataset`).
