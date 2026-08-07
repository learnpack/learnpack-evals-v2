# ADR-0020 — The shape of each datum is declared and verified: mandatory `value_domain`

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Design ·
Content Profiling

## Context

ADR-0014 gave **identity** to the data the criteria require: stable ids minted on the
demand side, with a mandatory definition written in that act, and adapters declaring
capabilities against those ids. The match is by id identity, never by strings.

What that ADR did not close is the **shape**. Until now, what shape the value of each id
takes lived only in the prose of its `definition` ("as a list where each entry carries the
lesson identifier, slug, position, type and title"). Nothing verified that what an adapter
produced had it. The contract held by social coincidence: the same person wrote the
adapter and will write the assessor.

The risk is **structural**, not a style omission. An automated assessor owes itself to an
**instrument**, not to a package format (ADR-0016, refined by ADR-0019): the same
executor runs over profiles produced by any adapter declaring the id that criterion
requires. A second adapter covering `lesson_inventory` with other field names produces
two outcomes, and the worse one is not the noisy one:

1. The executor blows up — valid profile, evaluation down. Visible.
2. The executor reads `None` where it expected an identifier, its parsing fails and the
   criterion emits **`fail` with a quote**. A reported generator defect that never
   existed, entering the judgment and the study, and disputable as an "instrument
   defect" when in reality it was a shape disagreement between two adapters.

(2) breaks from underneath the guarantee the rest of the design is built on: **without a
quote it is not evidence** (ADR-0009). A correct quote over a malformed value satisfies
the letter of that rule and not its purpose.

The `data_requirements.value_domain` column existed since migration `0005`, traveled
through the DTO and was parsed by the import — always `null`, with no owner and no
consumer. Block 6 (automated evaluation) is its first real consumer: it is the moment
the shape stops being prose and becomes an assumption inside an executor.

## Decision

**The shape of each datum is declared where the id is minted, is mandatory, and is
verified at the single point all adapters pass through.**

1. **`value_domain` mandatory on every `DataRequirement`**, written in the same act as the
   `definition` (ADR-0014 clause 1): the definition says what the datum **means**, the
   value domain says what **shape** it takes. A requirement without a declared shape is
   not a valid requirement.
2. **Demand-driven vocabulary** (13-code §7.4), exactly what the minted ids
   consume today: `string · number · boolean · string_list · record · record_list`.
   `record`/`record_list` carry `fields` (name → domain), with **one level of recursion**,
   sufficient for the worst real case (`lesson_activities`).
   - **Required fields yes, extra fields allowed.** A `record` declares the fields that
     must be present and with what type; a field the declaration does not name is not a
     violation. This keeps the two versioning axes independent: an adapter that starts
     emitting one more field does not force a new instrument version. The scenario this
     decision defends stays covered, because the **required** fields would be missing.
   - **`nullable: true` is not optionality**: the field must be present and may be null.
     Same discipline as invariant 3 one level up (declared capability + absent data
     ⇒ explicit `absent` entry, never a missing row): an adapter says "I looked and there
     was nothing" by emitting null, not by omitting the key. Silence is never evidence.
   - **Deferred and named, not silent:** `enum`, `levels` and `citation` (13-code §7.4
     vocabulary) are not built — no id consumes them. Same criterion as
     `existential`/`m_of_n` in sufficiency.
3. **The grammar and the checker are shared kernel** (`app/shared/domain/value_domain.py`),
   not one module's domain: `validate_spec` (is the declaration well-formed?) and
   `check_value` (does the value satisfy it?). Evaluation Design imports the first when
   minting; Content Profiling the second when profiling. One grammar, impossible to drift.
4. **Verification lives in `ContentProfile.ok()`** — the chokepoint every
   adapter passes through — as **invariant 5** of the aggregate, alongside the existing
   ones. An `absent` entry is not checked: it has no value and the absence is already
   the finding.
5. **A violation is `InvalidProfile`**, the same treatment as the aggregate's other
   invariants (capabilities outside the namespace, missing entries): an
   adapter ↔ namespace disagreement is a contract error to fix, not a datum to record. A
   profile with the wrong shape is not persisted.
6. **Rows without a value domain are deleted** (migration `0008`), not backfilled: the
   namespace is re-created with `import-instrument`, which is where value domains are
   authored. Admissible for the same reason 13-code §2 gave for the rubric/evaluation
   tables — they are experimental-phase data and no study has pinned an instrument
   version yet. It also retires the orphaned `practice_exercises` from an earlier draft.

## Relationship with ADR-0014

**It does not supersede it: it completes it.** ADR-0014 decides **where ids are born and
who has semantic authority** (the demand), and that stays intact — including the
definition lint, the aliases, the dictionary as a generatable view and the non-canonical
extras. This ADR adds **what else is declared in that same minting act** and **who
verifies that the supply meets it**. The reversal triggers of ADR-0014 (recreating the
registry with governance) remain in force as is; if any fires, the `value_domain` travels
with the id.

## Consequences

- (+) The shape disagreement between demand and supply is detected at the extraction edge,
  not months later inside an executor — and never as a quoted `fail` over a defect that
  does not exist.
- (+) The declaration of a `data_requirement` becomes the complete contract (meaning +
  shape), which is what an adapter author needs to implement a capability without
  asking.
- (+) The real cost was low: the column, the DTO and the import parsing already existed.
- (−) **On the automatic path the violation is silent.** The dispatcher catches every
  policy exception and only logs (ADR-0003: the event remains durable and the policy can
  be reprocessed), so an on-register profiling that violates the shape leaves no row and
  no event. It is detected on the manual path (`profile-content`, `reprofile`, which
  report the error per content) and in the fixtures test. No alerting is built: the
  decision is to accept it while the volume is that of a calibration phase.
- (−) Already-persisted profiles are not re-verified: the repository reconstructs them
  with the constructor, not with `ok()`. Deliberate — a stored profile is a past fact, it
  is not retroactively invalidated; regenerating them is `seed-demo --reset` or a new
  adapter version.
- (−) The declared shape is only as good as the discipline of whoever writes it. Mitigated
  with the test that runs every entry extracted from the frozen packages against the value
  domain of the instrument the team authors: changing one without the other fails there.
- (−) Strict `nullable` (present and null, not absent) is more demanding than JSON
  intuition and will surprise some adapter author. It is the price of omission never
  being a way of saying "there was nothing".

## Alternatives considered

- **Leaving `value_domain` optional, verifying only if declared** → rejected: forgetting
  to declare it is enough to return exactly to the state this ADR corrects, and the
  omission leaves no trace. Mandatoriness is what turns the shape into a contract.
- **A checker duplicated in each module** (pure Conformist: the spec crosses as data and
  each side interprets it with its own grammar) → rejected: the dispatch by type name
  would exist twice, and two grammars that must match with nothing tying them is the same
  drift problem ADR-0014 solved for the ids. The shared kernel is deliberate coupling to
  **one format grammar**, not to the other module's domain.
- **Recording the violation as a `failed` profile** instead of `InvalidProfile` → rejected:
  a `failed` profile says "the package could not be read", which is a condition of the
  evaluand; a shape disagreement is a code bug. Recording it as data normalizes it. (The
  counter-argument — that it cuts a batch short — does not apply: `reprofile` already
  catches `InvalidProfile` per content and continues.)
- **Adopting JSON Schema** → rejected: it solves a much bigger problem than the one at
  hand (composition, refs, conditionals) and its surface invites expressing semantic
  constraints that belong to the criterion's `pass_condition`, not to the datum's shape
  (ADR-0010). Six ids do not justify a dependency or its learning curve. The way back is
  cheap if one day it is needed: the grammar here is a subset expressible in it.
- **Validating the shape inside each assessor executor** → rejected: it moves the check
  downstream of the point where the datum is persisted as evidence, duplicates it once
  per executor and leaves the malformed profile in the database anyway.

## References

ADR-0009 (without a quote it is not evidence — the guarantee this protects) · ADR-0014
(the ADR this one completes) · ADR-0010 (normative thresholds live in the `pass_condition`,
not in the shape) · ADR-0016 and ADR-0019 (the assessor owes itself to the instrument, not
to the format — where the risk comes from) · 12-define §Content Profiling (invariants 1–4
of the aggregate) · 13-code §7.4 (the minimal spec this ADR realizes and narrows) ·
`docs/seed/instruments/learnpack-course-qa-v1.yaml`
(the six value domains, derived from what the `LearnpackV1` adapter actually produces).
