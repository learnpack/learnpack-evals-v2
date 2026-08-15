# ADR-0045 — The local setup replays acts the team already decided, and only in local mode

**Status:** accepted · **Date:** 2026-08 · **DDD context:** cross-cutting (Evaluation Design ·
Content Profiling · Evaluation · Evaluand Registry)

## Context

Three acts stand between a migrated database and one that can measure anything, and all three
are deliberately human: **publishing an instrument version** (ADR-0012 — the evidential
argument is validated and the version becomes immutable), **accepting a format's extraction**
(ADR-0012 — somebody read sample profiles and vouched for the adapter), and **ratifying an
assessor against an instrument version** (ADR-0019 — somebody confirmed this executor realizes
that criterion's text). Design 12's invariant 5 states the principle they share: nothing
produced by assistance reaches Published without a human act.

`task setup` does none of them. It migrates, seeds the rubric and the pedagogical reference
data, and runs `seed-demo` — three users, two frozen courses and an open campaign, which is
the *human* MVP's demo and has nothing to do with measuring a generator. Everything the
automated path needs is left as a sequence of commands to be discovered by reading
`backend/README.md`: two `import-instrument`, two `publish-instrument`, two
`accept-extraction`, three `ratify-assessor`, one `register-generator`. Until they are run,
`/admin/assessors` shows three packages that no `assessors` row exists for, every instrument
is a draft, and `evaluate` refuses.

**That is not a documentation problem.** The system is about to be handed to someone whose job
is to run generations against it — a collaborator outside the team, and later any team that
clones the repo to measure its own generator. For them the first act is not "decide which
instrument is right"; it is "get the one this repo already calibrated, and start measuring".
The decisions those ten commands encode were made once, argued in the instrument headers and
in fourteen calibration runs, and written down in the repository. Retyping them is not
deciding anything.

**And repetition is not idle: it is where a workbench diverges.** The commands must run in the
right order, against the right version ids, with the right admin — and nothing checks that
they did. A database where `drafts-hybrid` was ratified against v5 while the console publishes
v6 is a database that measures with a norm nobody chose, and the only symptom is a refusal
much later, in the middle of a paid batch.

The counter-pressure is real and is why this needs a decision rather than a commit: an
automated publish is an automated *human act*, and if it can run anywhere it hollows out three
invariants at once.

## Decision

**A declared manifest names the artifacts a local workbench is built from, and one command
replays the acts that install them — under the local-mode gate, attributed to the local admin,
deciding nothing the manifest does not already say.**

1. **The manifest is data, in `docs/seed/workbench.yaml`.** It declares three lists:
   instrument versions to publish (by file), package formats whose extraction is accepted, and
   generator lineages to register. It sits beside `rubric-v1.json` and
   `pedagogical-reference.yaml`, in the same file-based idiom the seeds already use, and it is
   reviewed like they are. Editing it is how a workbench changes; no code changes with it.

2. **`seed-workbench` applies it, and refuses outside `AUTH_MODE=local`.** The same gate
   `seed-demo` carries (ADR-0008), for a stronger reason: stray demo rows are a mess, whereas
   a published instrument or a ratification is a record of somebody's judgment. Local mode is
   already refused with `ENVIRONMENT=production` or a non-local `DATABASE_URL`, so the gate
   cannot be satisfied by a real store.

3. **Every act is attributed to the local admin**, an identity that exists only in local mode
   (`local|admin@local.dev`) and which the command creates if it is missing. The attribution
   columns keep meaning what they say — `published_by`, `accepted_by`, `ratified_by` name who
   did it — and in this database the answer is honestly "the local setup".

4. **What is replayed is the repetition, never the decision.** The command publishes exactly
   the versions the manifest names, accepts exactly the formats it lists, and passes no
   `--confirm` to a ratification: against a fresh store the first ratification of a lineage
   *is* the registration and asks nothing, and against a store that already has one, a changed
   executed criterion still demands the explicit confirmation ADR-0019 requires — the command
   fails there rather than confirming on somebody's behalf.

5. **One version per lineage, and the assessors follow from it.** The manifest publishes at
   most one version of an instrument lineage (two is refused, not resolved), and every
   automated assessor package in the code registry is ratified against the published version
   of its own lineage. Which assessors exist is the registry's answer (ADR-0016: adding a
   package is adding an assessor), so a new package needs no edit here to become usable — and
   a package whose lineage the manifest does not publish is reported and left unratified,
   which is what "nothing here decided it should judge" looks like.

6. **It is idempotent, and idempotent by asking rather than by swallowing.** An already
   published version is left alone (re-importing over one is refused — immutability, ADR-0012),
   an already registered lineage is reported instead of re-registered, an acceptance and a
   ratification already recorded say so. Swallowing the refusals instead would also hide the
   near-miss guard of ADR-0031 firing on a real typo.

7. **Courses and generator versions are NOT in the manifest.** Both are facts about a run, not
   about the workbench: courses come from wherever the generator wrote them, and the version is
   read off the folder each generation is registered from. A file checked into the repository
   must not claim to know either.

8. **`seed-demo` stays, and leaves the setup.** The human MVP's demo is still a command
   anybody can run; it is no longer what `task setup` installs. The two seeders answer
   different questions — "show me the evaluator flow" and "make this database able to
   measure" — and merging them would give every operator two courses and a campaign that are
   not theirs.

## Consequences

- (+) A rebuilt database is a working one. `docker compose down -v` → migrate → `seed` →
  `seed-workbench` is a complete, repeatable path to a store that can measure, which is what
  makes starting from zero a routine act rather than an afternoon.
- (+) The workbench becomes reviewable. Which instrument version this repo measures with, and
  which formats it reads, is one file in a diff instead of an oral tradition.
- (+) It is the framework's first contract kit for another team: clone, edit three lists, run
  one command.
- (−) An automated act with a human's name on it. Mitigated by the gate and by clause 4 (it
  only ever installs what the manifest names), but the attribution in a local database says
  "admin@local.dev" for something no person did that day. Accepted: in a store that only
  exists on one developer's machine, the alternative is not more honest — it is unrun.
- (−) The manifest can go stale against the code registry: an assessor bumped to a version
  whose coverage does not decide every criterion of the published instrument version fails the
  command. That failure is loud and at setup time, which is where it should be, but it does
  make `seed-workbench` a gate the test suite does not cover.
- (−) Two ways to publish an instrument now exist (the console button and this). They call the
  same use case, so they cannot disagree about what publishing means; what they can disagree
  about is which version is current, and clause 5's one-per-lineage rule is what keeps the
  manifest the answer.

## Alternatives considered

- **Leave the acts manual and write a better runbook** → rejected: that is today, and today is
  the reason the system cannot be handed over. A runbook is a list of ten commands whose order
  matters and whose version ids must be typed correctly; the failure it produces is a store
  that looks set up and measures with the wrong norm.
- **Fold it all into `seed-demo`** → rejected: the demo installs an evaluator campaign and two
  frozen courses from the human MVP. An operator measuring their own generator would start with
  someone else's data in their store, and every "is this mine?" question afterwards would be a
  real one.
- **Put the manifest's content in code** (a constant beside `AUTOMATED_ASSESSORS`) → rejected:
  which instrument version a workbench measures with is a decision that changes with every
  bump, made by whoever owns the instrument. Code is where the artifacts live; the choice among
  them is data, and it is the same argument ADR-0012 made when instrument authoring became
  file-based.
- **Publish without the local-mode gate, on the grounds that a manifest in the repo is already
  a reviewed act** → rejected: the review that matters happens when a person decides that THIS
  store should carry that norm. A gate that can be satisfied on a production database turns
  three invariants into a configuration detail.
- **Have the manifest name the assessors and their versions explicitly** → rejected: it
  duplicates the code registry, and the duplicate goes stale in the one direction that hurts —
  a bumped assessor that the manifest still pins to its old version would leave the new one
  unratified and the old one permitted, silently. Clause 5 derives it instead.

## References

ADR-0012 (instrument publication and extraction acceptance as human acts; authoring is
file-based — the idiom the manifest joins) · ADR-0019 (ratification per instrument version, and
the confirmation a changed executed criterion demands — clause 4 refuses rather than supplies
it) · ADR-0016 (the in-code assessor registry: adding a package is adding an assessor — what
clause 5 derives the assessor list from) · ADR-0008 (local mode, and the conditions that keep
it off a real database — the gate of clause 2) · ADR-0007 (roles and the first admin; logging
in never changes a role — why the seeder aligns it explicitly) · ADR-0031 (a lineage's name is
typed once, guarded against a near miss — why clause 6 asks instead of swallowing) · ADR-0024
and ADR-0027 §5 (the generator and the courses are declared per run, not per workbench —
clause 7) · design 12 invariant 5 (nothing from assistance reaches Published without a human
act — the principle this bounds rather than removes).
