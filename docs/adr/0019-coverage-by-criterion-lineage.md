# ADR-0019 — Assessor coverage by criterion lineage: ratification per version without identity change

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Pedagogical Evaluation ·
Identity · Evaluation Design

## Context

ADR-0016 (clause 3) ties each automated assessor to **one version** of an instrument
(`instrument_version_id`); ADR-0018 refined what that tie requires (complete declaration:
mapping ∪ abstentions == target criteria). The consequence ADR-0016 already noted —
"a new criterion in the target demands a new version of the assessor" — turned out, in the
realization, to be considerably wider: **any new version of the instrument** forces a new
version of every assessor that targets it, even when the change touches no criterion
that assessor executes (or touches only criteria it abstains from) and its code remains
byte-identical.

That contradicts the argument of ADR-0016 itself, which rejected the shared check
library for **spurious identity churn** ("any change in any function changed the identity
of all judges at once — spurious invalidation"). Per-version targeting reproduces that
churn at instrument granularity: the assessor's identity dies — and with it its
calibration, which "does not transfer" by rule — when nothing the assessor is or does
changed. The calibration of an identical artifact judging identical criteria **does**
transfer; invalidating it is incorrect, not just laborious.

The cost lands exactly where iteration is heaviest: the calibration phase of an instrument
(`learnpack-course-qa-v1` is the present case) produces versions in rapid succession —
every wording or threshold tweak is a new version, because published is immutable — and
each one drags a ceremonial bump of all its assessors.

The substrate for something better already exists by design: `claimId`/`criterionId` are
**stable across versions** (lineage, 12-define §Evaluation Design inv. 1) — precisely so
that other pieces can refer to a criterion across versions.

## Decision

**The automated assessor's coverage is declared over the criteria lineage of its
instrument; its validity for each concrete version is established by an explicit act of
ratification, which does not change the assessor's identity.**

1. **The assessor owes itself to an instrument (lineage), not to a version.** Its
   declaration is `instrument_id` + coverage per `criterion_id`: `criterion_id → executor`
   mapping ∪ abstentions, disjoint sets (ADR-0018, intact) — keyed by the stable ids of
   the lineage.
2. **Ratification per version.** An assessor is eligible to evaluate against an instrument
   version only if that version is **ratified** for it. Initial registration
   ratifies the first version with the ADR-0018 validation as is: coverage
   (restricted to that version's criteria) == the version's criteria, with no overlap.
3. **Compatibility computed; human decision only on the delta.** Ratifying a new
   version mechanically computes the diff over the lineage:
   - A criterion whose **normative text realized by the executor** (`pass_condition` +
     `required_data`, literal comparison) is unchanged → its coverage entry
     (executor or abstention) is preserved without intervention.
   - A **new or changed** criterion → requires an explicit decision by the author before
     the ratification proceeds: abstain · confirm that the existing executor realizes the
     new text (norm/realization consistency is verified by the human layer 2,
     ADR-0016 clause 6) · or change the executor — which is a change of the artifact and
     therefore a **new assessor version** (clause 2, intact).
   - Criterion fields realized by the **mechanical derivation**, not by the executor
     (`on_missing_evidence`, `condition`), and the instrument's bindings, do not
     invalidate coverage.
4. **Identity is untouched.** The assessor's version remains the identity of its
   software artifact (code, mapping, config): any change of the artifact ⇒ new
   version ⇒ another identity (ADR-0016 clause 2). Ratifying instrument versions is not
   a change of the artifact; calibration transfers over identical criteria and is
   invalidated only where something truly changed.
5. **The forcing function stays.** No criterion reaches an evaluation without a
   conscious decision by the assessor's author: an unratified version is not evaluable
   by that assessor (`EvaluateContent` requires an assessor with the requested version
   ratified), and each ratification's delta requires an explicit decision — the purpose of
   ADR-0016 §3 and of ADR-0018, now at a cost proportional to real change.
6. **Realization deltas over 13-code §3.5** (frozen snapshot this ADR
   amends): the assessor's `source_config` declares `instrument_id` + coverage per
   `criterion_id` (not an `instrument_version_id`); a persisted relation of
   ratifications appears (assessor × instrument version, with actor and date —
   ratification is a human act, via a CLI that shows the diff and asks for the delta
   decision); the "at registration" validation of ADR-0016/0018 becomes the initial
   ratification. The exact shape of tables and commands is decided by block 6. Coverage
   entries for criteria a version no longer has are inert for that version (like
   orphaned `data_requirements`: the lineage does not delete).

## Relationship with ADR-0016 and ADR-0018

**It does not supersede them.** From ADR-0016, the `human | automated` taxonomy, the
assessor as a versioned modular artifact, invalidation by identity **of the artifact**
and the 100% declarative instrument remain in force; this ADR refines its clause 3:
"declares a target instrument (one version)" becomes "owes itself to a lineage and
ratifies versions". From ADR-0018, the abstentions, the `not_assessed` state and the
disjoint-union validation remain in force; what changes is the object of that validation:
from a single target version to each ratified version.

## Consequences

- (+) The spurious churn dies: a new instrument version costs each assessor a
  ratification (diff + decision on the delta), not a new identity. The instrument
  calibration phase (cheap versions in succession) stops leaning its cost on
  the assessors.
- (+) Calibration transfers exactly where it should — more faithful to the
  invalidation-by-identity principle of ADR-0016 than the rule this ADR refines.
- (+) It is recorded **who decided what about each delta** (ratification is an act with
  actor and date), instead of being implicit in a version bump.
- (−) One more relation to persist and query (ratifications) and one more CLI command.
- (−) The normative-text comparison requires stable canonicalization (literal
  comparison; any wording tweak of a `pass_condition` counts as a change and
  asks for a decision — a cheap false positive preferable to silent drift).
- (−) "Instrument 1 → 0..N assessors" now reads by lineage; knowing which assessor can
  evaluate which version requires querying ratifications, not just `source_config`.

## Alternatives considered

- **Keeping the per-version target (ADR-0016/0018 literal)** → rejected: it invalidates
  identity and calibration with byte-identical code — spurious churn by the argument of
  ADR-0016 itself.
- **Automatic compatibility without ratification** (new criteria derive implicit
  `not_assessed`) → rejected: a new criterion would pass without a conscious decision —
  exactly what ADR-0016 §3 meant to prevent — and an omission bug again becomes
  indistinguishable from a known limitation (the ADR-0018 argument).
- **Making the bump cheaper** (auto-generating the new assessor version with the updated
  target) → rejected: it automates the ceremony instead of eliminating it; it still
  fragments identity and calibration without real cause and pollutes the assessor history
  with change-less versions.
- **Target by `instrument_id` without per-version ratification** → rejected: silent
  drift — the assessor would "cover" versions it never saw.

## References

ADR-0016 clauses 2, 3 and 6 (the refined clause and the ones this ADR preserves) · ADR-0018
(abstentions and `not_assessed`, in force; their validation changes object) · 12-define
§Evaluation Design inv. 1 (id lineage — the substrate) · 13-code §3.5 (the realization
this ADR amends) · the `learnpack-course-qa-v1` instrument and its calibration phase (the
case that exposed the churn) · versioning rigidity analysis session (notes/, cycle
complete).
