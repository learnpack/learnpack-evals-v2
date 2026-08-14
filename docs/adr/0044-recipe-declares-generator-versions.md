# ADR-0044 — A study's recipe declares which generators it measures

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluation Studies

## Context

A study's recipe is a list of briefs, and the dataset is whatever the registry has registered
from them: `_Selecting._materialize` calls `get_contents_by_briefs(brief_ids)` and keeps every
row it answers. Nothing in that path mentions the generator.

**So a round that means to measure one version silently measures two.** A brief is a
commission, and the same commission is handed to a new version of the generator precisely when
somebody wants to know whether the new version is better — that is the ordinary case, not an
edge one. Select that brief and both versions' courses enter the dataset. The system is not
missing an answer; it is producing a mixed one that nobody asked for and no surface names. The
report's `generatorLevel` and the fitness projection's per-version grain do break the numbers
down afterwards (ADR-0023), but the round's own header pools them, and the person reading it
has no way to know that the population was two populations.

**And the comparison this makes impossible to state is the one the system exists for.**
Internal QA of generators (ADR-0012, the purpose the instrument was born from) asks two
questions: *does this version hold the bar*, and *does the new version beat the old one*. The
second has never had a way to be set up. Today it can only be approximated by two studies,
which is the weakest possible form of it: two datasets, two moments, and — unless somebody is
careful by hand — possibly two instrument versions and two judges, which is exactly the triple
ADR-0042 made a study's result be defined by.

**The two questions are one mechanism with two arities.** Measuring a version is briefs × one
generator version; comparing is briefs × N. The recipe has one axis and needs a second.

## Decision

**A study declares which generator versions it measures. The declaration is the recipe's
second axis, it is required, and how many versions it names is what makes the round a
measurement or a comparison.**

### 1. The scope is one field with two forms

1. **`generator_scope` is either `"all"` or a non-empty list of generator version ids.** One
   field, so it cannot contradict itself; two forms, so "every version these briefs bring" is
   something a person says rather than something the absence of a filter means. An empty list
   is refused at the boundary — it would select nothing, and it is the one value that could be
   read as either form.

2. **It is required, and `open()` refuses without it**, beside `InstrumentNotChosen` and
   `AssessorNotChosen`. The scope becomes the fourth thing opening fixes, and `prepared` — the
   derived "everything opening needs is here" — waits for it like it waits for the other
   three. Until then it replaces freely, exactly as ADR-0043 §1 decided for the other choices:
   nothing can consume it before the study opens.

3. **The declaration is ADR-0024's rule applied to the recipe.** That decision refused to let a
   content's generator be defaulted, because "the system whose purpose is generator QA loses,
   without a word, the very key it is about". A recipe that silently spans every version loses
   the same key at the other end of the same axis. The cure is the same: say it, or be refused.

### 2. The dataset stays derived, and the pairing is why

4. **Courses are never picked one by one.** The dataset remains `briefs × scope`, materialized
   by the registry. Comparing versions is only meaningful over the same commissions — the
   GLOSSARY already requires `CompareStudies` to pair sets by briefs — and a hand-picked list
   of contents breaks that pairing without saying so. The brief axis is what makes the
   comparison an experiment rather than two samples.

5. **A commission that produced courses for one version and none for another is reported, not
   filtered.** ADR-0039 settled this shape for the report — "a commission that produced no
   course reads as an empty group instead of vanishing" — and it holds here for the same
   reason: an unpaired commission is a fact about the comparison, and it can only be acted on
   while the study is still a draft.

6. **An explicit list excludes contents whose generator is `unknown`**, as a consequence of
   naming versions rather than as a rule of its own. `"all"` keeps including them, which is
   what every study composed before this decision did.

### 3. Unequal coverage is declared, never refused

7. **Two versions whose packages are in different formats may be compared.** Nothing about the
   arithmetic breaks; what breaks is the comparability of the two numbers, because coverage is
   per format (a criterion with no datum to read is `not_assessed`, and ADR-0018 §4 and
   ADR-0023 §7 keep that state out of the denominator). Two formats therefore give two
   denominators.

8. **So the console and the fitness projection say so, and neither blocks.** This is 12-define
   invariant 1 — readiness informs, it never blocks — and it is the same treatment ADR-0023 §7
   already gives to two assessor sets with different coverage: the values are published with
   what they were computed over, and the consumer is told when a difference between them is
   not interpretable.

### 4. What this does not build

9. **`purpose` stays unbuilt, and this is the decision that would have been its first
   consumer.** The typology the GLOSSARY reserves (initial / regression / comparison) would
   here be a second declaration of something the first already says: a scope naming one version
   is a measurement, one naming several is a comparison. Two fields that must agree is the
   defect ADR-0043 §8 removed from the setup screen, and a study labelled *comparison* whose
   scope names one version would be exactly that defect with a new spelling. **The arity is the
   typology.** ADR-0043 §7 stands.

10. **The comparison is read where optimization is read.** ADR-0023 built the per-generator-
    version grain as a signal for the genetic-algorithm experiment and kept it out of
    `study_reports` deliberately. That is where two versions are compared: the QA report answers
    whether a round clears the bar, and the fitness projection answers which version rides
    higher. Nothing is added to the frozen document, so `SCHEMA_VERSION` does not move.

11. **`CompareStudies` stays derived and unbuilt.** A comparison inside one study needs no
    entity: the instrument version, the judge and the moment are shared by construction, which
    is the strongest form of the control that comparing two studies would have to reconstruct
    by hand.

### 5. The backfill states a fact rather than guessing one

12. **Every study that exists is backfilled to `"all"`.** This is not the judgement call
    ADR-0042's backfill had to make. Those rows' datasets *were* materialized without a
    generator filter, so `"all"` is a description of what happened, not an inference about what
    was meant. Drafts are backfilled too and cost nothing by it: a draft is editable by
    definition, and the scope can be corrected before it opens.

13. **The column has no default, and a third value — none at all — belongs to drafts only.**
    An undeclared scope is a legitimate half of a draft and an impossible study, so it is
    stored as `NULL` and refused by `open()`, exactly as an unchosen instrument is. A default
    would have been the cheaper backfill and would have let an insert that forgets the field
    mean "all" silently — the defect this ADR closes, reintroduced one layer down. The
    backfill is therefore an explicit one-time statement about the rows that exist, not a
    rule that outlives them.

## Consequences

- (+) A round that measures one version measures one version. The mixed dataset is
  unreachable, not merely visible.
- (+) An A/B comparison is a thing somebody can set up, over one dataset, one instrument
  version and one judge — the triple ADR-0042 defined a result by, shared by both sides.
- (+) The recipe now says out loud what the fitness projection was already computing per
  version, so what is measured and what is read stop being discovered separately.
- (−) **`declare-study` without a scope now refuses**, and the scripts that drive generations
  from the CLI have to name one. The refusal is the point of clause 2 and the cost is real: it
  is a breaking change to a contract in use.
- (−) A required field in a form is one more thing between a person and a round. The mitigation
  is that *All versions* is one click and says what it does.
- (−) The recipe has two axes, so a draft can be in a state where the briefs are right and the
  scope is not, and the dataset must be re-materialized whenever either moves. That is one more
  invariant for the application to hold, and it is held in one place.

## Alternatives considered

- **Declare a `purpose` (initial / regression / comparison) and let it drive the form** →
  rejected, clause 9. It is a second source of truth for something the scope already says, and
  its failure mode is a label that disagrees with its dataset.
- **Make the scope optional, with an empty list meaning every version** → rejected, and it was
  the tempting one: it breaks no script and needs no backfill. It also leaves the silent
  mixture reachable by omission, which is the whole defect. A warning on a screen is not a
  substitute for a declaration when the CLI is a first-class door (ADR-0008) and the accidental
  case is the ordinary one.
- **Let the recipe name contents directly, filtered by version in the UI** → rejected, clause
  4. It gives the same dataset for the single-version case and quietly destroys the pairing in
  the comparison case, where nobody would notice until the numbers were already read.
- **Run A/B as two studies and build `CompareStudies`** → rejected, clause 11. It is more
  machinery for a weaker guarantee.
- **Refuse a scope whose versions are in different formats** → rejected, clause 8. The
  comparison is legitimate and sometimes the only one available (a generator that changed its
  output format is exactly the change worth measuring); what is illegitimate is subtracting two
  numbers computed over different denominators, and that is said, not prevented.
- **Attach the scope per brief rather than to the recipe** → rejected: it expresses a
  cross-product nobody has asked for, and the pairing that makes a comparison valid is the same
  scope over every commission.

## References

ADR-0024 (the generator link is declared, never defaulted — the rule this applies to the other
end of the axis) · ADR-0031 (a generator is an entity and its versions belong to it — what a
scope names) · ADR-0039 (the brief is a grouping axis; nothing is pooled per brief, and an
empty commission is reported rather than dropped) · ADR-0023 §7 (coverage travels with every
fitness value, and only equal coverage may be compared — why clause 8 warns) · ADR-0043 §1
(a draft chooses, opening pins — the lifecycle the scope joins) and §7 (`purpose` returns to
the GLOSSARY and stays unbuilt — reaffirmed here) · ADR-0042 (a study's result is a triple, and
the backfill that filled only the unambiguous — contrasted in clause 12) · ADR-0018 §4 and
ADR-0012 (the purpose the instrument was born from) · 12-define invariant 1 (readiness informs,
it never blocks) · 13-code §3.6 (the recipe as briefIds — amended here) · GLOSSARY
(`EvaluationStudy`, `CompareStudies`).
