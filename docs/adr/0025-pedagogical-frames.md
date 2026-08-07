# ADR-0025 — The pedagogical vocabulary is a frame, and frames are disjoint namespaces

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Design ·
Evaluation Studies · Golden Dataset

## Context

The system was conceived to evaluate **different kinds of educational content** under
**different pedagogical approaches**. The first axis has a mechanism: `PackageFormat` plus
profiling adapters translate a foreign package into `DataRequirement`s (ADR-0012, ADR-0017).
The second axis has none.

Today there is exactly **one** pedagogical vocabulary, and it is implicit. `pedagogical_dimensions`
and `qualities` are flat global tables with no grouping key, no version and no lifecycle
(migration 0005). They are loaded by upsert from a single `docs/seed/pedagogical-reference.yaml`
— an upsert that never deletes, so removing a quality from the file does not remove it from the
store. Every instrument validates its claims against *all* qualities that happen to exist:
`InstrumentVersion.publish()` receives `known_qualities` meaning "everything in the database".

Three consequences follow, and they are why this is decided now rather than when a second
approach appears:

1. **There is no way to say which approach an instrument belongs to.** Two approaches
   coexisting would be one flat set in which nothing prevents a claim from anchoring in a
   quality that belongs to the other approach's logic.
2. **Changing the vocabulary is an in-place mutation with retroactive reach.** Re-parenting a
   quality to another dimension is a one-line edit that silently changes the dimension-level
   reading of every study already published. This is what forces the instrument to freeze the
   `quality → dimension` map at publish (clause 4 below).
3. **The absence has never been visible** because a single global set is indistinguishable from
   no set at all. The fitness projection is the first consumer that reads *across* qualities and
   dimensions systematically, and it is what made the missing entity legible.

One distinction must be fixed before deciding, because it is the likeliest confusion:
`pedagogical_frameworks` (Merrill, Biggs, Revised Bloom, SOLO, Schmidt, Learning Progressions)
is **not** this. Frameworks are the `grounded_in` of a quality or criterion and the `warrants` a
claim cites — the scholarly provenance that justifies. They are bibliography, not vocabulary.

## Decision

**The pedagogical vocabulary is an explicit entity — a `PedagogicalFrame`, which owns its
dimensions and its qualities — and frames are disjoint namespaces.**

1. **A frame owns its dimensions and its qualities.** It is named, and it is what "a pedagogical
   approach" means in this system. The current set of 5 dimensions and 21 qualities becomes the
   first frame; nothing about it changes by being named.
2. **Frames are disjoint namespaces.** A quality belongs to exactly one frame; so does a
   dimension. Two frames that describe a seemingly similar quality **declare it twice**, each
   with its own id, its own definition, its own dimension and its own `grounded_in`. There is no
   sharing, no aliasing and no equivalence table between frames.
3. **An `InstrumentVersion` declares its frame when it is created**, and that declaration is
   immutable for that version. `publish()` validates the claims' `quality_ids` against **that
   frame's** qualities, not against the global set. The domain signature does not change:
   `publish()` already takes `known_qualities` as injected plain data — what changes is what the
   use case passes it. The seam is already where it needs to be.
4. **The instrument freezes its frame's relevant slice at publish.** The `quality → dimension`
   map of the qualities the instrument references is stored inside the published version. A
   published instrument is therefore self-sufficient: the frame may evolve afterwards and no
   already-published instrument, judgment or study changes meaning. This also keeps the bare ids
   already stored in `instrument_claims.quality_ids` resolvable — the instrument's own frame
   declaration disambiguates them, which is what disjointness would otherwise make ambiguous.
5. **This is not a port, and it is not an adapter.** Ports exist where there is a boundary to
   cross and an implementation that varies: packages, LLMs, storage. A frame is reference data of
   the domain — nothing to translate, nothing foreign, no second implementation. A port here
   would be indirection without a frontier.
6. **The two axes stay orthogonal.** `DataRequirement`s describe what a package *supplies* and are
   frame-independent; claims and qualities describe what is *asserted* and are frame-scoped. A
   content format and a pedagogical approach compose freely, and the criterion — which consumes
   data requirements to evidence a claim — is the join between them. Frames never touch execution.
7. **Comparability is frame-scoped, at every grain.** Results anchored in different frames are not
   comparable: not per dimension, and — this being the consequence of disjointness — not per
   quality either. A study line pins its frame exactly as it pins its instrument and its formula.
   For the genetic-algorithm experiment this reads: **changing frame starts a new experiment, not
   a new generation.**
8. **Frameworks stay global and shared.** Several frames may cite Merrill. A citation asserts
   provenance, not equivalence of meaning, so sharing costs nothing there — which is precisely the
   asymmetry that makes disjointness right for qualities and wrong for frameworks.
9. **The mechanism is not built ahead of a second frame.** Until a second pedagogical approach
   genuinely exists, the current vocabulary is the implicit first frame and no table, column or
   validation changes. What this ADR fixes now is the shape, so the decisions taken meanwhile —
   clause 4 above in particular — do not have to be undone.

## Why disjoint rather than shared

The alternative was a common pool of qualities from which each frame selects, plus its own
partition into dimensions. It was preferred on first analysis, for two real gains: no
duplication, and per-quality comparability surviving a change of frame. It is rejected for four
reasons.

- **A shared id would assert an equivalence nobody verified.** Two approaches that appear to
  share a quality usually do not quite: the definition differs, the anchoring differs, the
  evidential expectation differs. This is ADR-0011's incommensurability argument one level down —
  the same reason distinct criteria cannot be averaged is the reason two approaches' qualities
  cannot be silently identified.
- **Meaning would depend on the reader.** With a shared pool, one quality id would sit under
  different dimensions depending on which frame is looking. The id would stop naming one thing,
  and `qualityId` is exactly what the design relies on for thematic continuity across instrument
  versions (GLOSSARY, 12-define §70).
- **It would create shared governance with no owner.** Changing a definition in the pool means
  knowing every frame that depends on it. ADR-0022 already rejected a mechanism for exactly this
  shape of reason: *coordination does not scale and erodes silently*. A small team has no way to
  answer "who may change this definition, and who must be told".
- **A frame becomes reviewable as one piece.** Its definitions, its partition and its anchoring
  belong to one pedagogical logic and can be read, edited and criticized without tracing
  dependencies out of it.

What this costs is stated plainly in the consequences, not argued away.

## Consequences

- (+) The pedagogical approach stops being implicit. It can be named, cited in a report, and
  chosen deliberately when an instrument is written.
- (+) A new approach is **additive**: it is declared alongside the existing one, with no
  re-parenting and no renaming, so the retroactive-mutation risk of the current flat set
  disappears for every frame already in use.
- (+) Publish validation gets sharper. Today it can only say "unknown quality"; frame-scoped, it
  also catches "a quality from another frame" — which is the mistake someone will actually make.
- (+) The instrument snapshot (clause 4) makes frame evolution safe by construction rather than by
  discipline, which is the standard this repo already holds elsewhere (ADR-0017).
- (−) **No comparability across frames, at any grain.** A shared pool would have kept a comparable
  per-quality series for the qualities two frames had in common; disjointness gives that up. Every
  historical series — including the fitness projection's — restarts when the frame changes.
- (−) **Duplication, and drift that is invisible.** Two frames that genuinely share a quality
  maintain two copies. Nothing detects that they have diverged, and nothing should: under clause 2
  they were never the same quality.
- (−) **Human reference data does not transfer between frames.** ADR-0015's panel judges
  *qualities* directly, and its whole economics is "labeled once, reused on every iteration". Under
  disjoint namespaces the reference is bought **per frame** — a real and recurring money cost,
  and the strongest practical argument the shared pool had.
- (−) Ids become unique per frame rather than globally, so the store gains a composite key and
  every reader of a bare quality id must know the frame it belongs to. Clause 4 is what keeps this
  from reaching already-published instruments.
- (−) Seeding grows a dimension: one reference file becomes one file per frame, and `seed_reference_data`
  must stop meaning "the vocabulary" and start meaning "this frame's vocabulary".

## `[future]`

- **A crosswalk between frames** (declaring that quality A of frame X corresponds to quality B of
  frame Y) would restore some cross-frame comparability. It is deliberately **not** deferred as a
  neutral option: a crosswalk is the shared pool wearing a disguise, and it reintroduces every
  reason clause 2 exists. It must not be added without an ADR that answers what the correspondence
  claims, who verified it, and what it licenses anyone to compare.
- **Frame versioning.** Clause 4 makes published instruments immune to frame drift, which removes
  the urgency; a frame that changes substantially can also simply be a new frame. Whether a frame
  needs its own version line is a question for when one is edited in anger.

## Alternatives considered

- **Shared pool of qualities + per-frame dimension partition** → rejected; see "Why disjoint
  rather than shared" above. It was the better answer on comparability and duplication and the
  worse one on meaning and governance.
- **A port with an adapter per pedagogical approach** → rejected: there is no boundary to
  translate and no varying implementation. The analogy with the content axis is tempting and
  false — packages are foreign and must be converted, a vocabulary is ours and must only be
  scoped.
- **A single global vocabulary, versioned** → rejected: versioning answers *how did it change*,
  not *which approach is this*. Two approaches would still share one flat namespace in which
  nothing prevents a claim from anchoring across them.
- **The frame as a property of the `Study` rather than the `InstrumentVersion`** → rejected: it is
  the claim that anchors in qualities, and claims belong to the instrument. Declaring the frame on
  the study would permit a study whose instruments belong to different frames — the exact
  incoherence clause 7 exists to prevent. A study inherits its frame by pinning its instrument.
- **Leaving the vocabulary flat and treating "approach" as a naming convention on ids**
  (`merrill:objectives-observable`) → rejected: it puts the grouping in a string nothing
  validates, and publish would still accept a claim anchored in another approach's quality.

## References

ADR-0011 (no single aggregate score — the incommensurability argument this applies to the
vocabulary itself) · ADR-0022 (mechanical brief intake — the precedent that coordination does not
scale and erodes silently) · ADR-0015 (human reference panel per quality — the consumer that pays
the duplication cost) · ADR-0012 and ADR-0017 (the content axis: profiling adapters and the
declared surface — the orthogonal axis this one is deliberately not modelled after) · ADR-0023
(fitness projection — the consumer that made the missing entity legible, and where the frozen
`quality → dimension` map of clause 4 is first needed) · ADR-0020 (`value_domain`: reference data
that must be declared and verified, not assumed) · 12-define §Evaluation Design and 13-code §3.3
(frozen snapshots this ADR amends: they describe frameworks, qualities and dimensions as a single
global set of reference data referenced by id) · GLOSSARY (`PedagogicalDimension`, `Quality` — the
entries a realization of this ADR must complete).
