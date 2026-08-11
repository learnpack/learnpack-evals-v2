# ADR-0033 — Registered content is never retired; removing it is a development affordance

**Status:** accepted · **Date:** 2026-08 · **DDD context:** Evaluand Registry

## Context

Nothing in this system removes a registered content. There is no `ContentRetired`, no delete
endpoint, no CLI command — the only deletion that exists anywhere is `seed-demo --reset`,
which wipes the whole local dataset, and `delete_failed`, which drops a `failed` profile so the
manual path can retry and explicitly never touches an `ok` one.

That absence was never a decision. It is what an events-first model looks like when nobody has
needed the opposite yet: state evolves by appending, and removal was simply never written.

Developing against a generator whose package format is still moving made the need concrete. In
two days the format changed twice, and each change meant re-registering courses that were
already in the store. Doing it by hand required knowing six tables, two different cascade
behaviours, a column whose type is not the obvious one, and two references no foreign key
protects. It is a procedure that does not survive being repeated from memory.

Three facts shape what may be built, and they pull in different directions:

1. **A published `StudyReport` is immutable and freezes what it evaluated** (12-define inv. 3).
   Removing a content a published report names would leave a dangling reference inside a
   document that by design cannot be corrected. This is not a data-integrity inconvenience; it
   is the reproducibility promise the whole engine rests on.
2. **`study_dataset(study_id, content_id)` and `study_recipe(study_id, brief_id)` carry ids
   with no foreign key.** Composing a dataset crosses a module boundary, so the reference is by
   id rather than by constraint (ADR-0006). The database therefore *cannot* refuse a deletion a
   study depends on: it would succeed and rot silently.
3. **`GenerationBrief`s are shared.** Registration dedupes by `brief_hash`, which is the paired
   design — same briefs, new products (ADR-0013). A content's brief may be another content's
   brief, so removing content cannot assume its brief goes with it.

Fact 1 argues for never removing anything. Facts 2 and 3 say that if anything does remove
content, the checks cannot be delegated to the database and must be written down somewhere a
human does not have to reconstruct.

## Decision

**Content is never *retired*. It can be *deleted*, only in development, and only when nothing
has used it.**

1. **No retirement in the domain.** No `ContentRetired` event, no status on the aggregate, no
   policy. "Retired" would mean *excluded from new campaigns and studies, still available to
   published ones* — a production-hygiene concept that no current use case needs, and that
   would have to answer questions (does a retired content still count in a generator's fitness?
   may it be un-retired?) nobody is asking.

2. **Deletion is a development affordance, not a capability of the system.** One CLI command,
   `delete-content --content-id <id>`. **No endpoint**, so it has no production surface and the
   frontend never learns the concept.

3. **It runs only in local mode.** `AUTH_MODE=local`, which `Settings` refuses unless
   `DATABASE_URL` points at a local host (ADR-0008, validated at construction). One condition
   is enough because that coupling already exists — the same reasoning `seed-demo` documents.

4. **It refuses content that has been used, and the refusal is checked in code.** Evaluated,
   assigned, in a campaign, quorum-completed, or named by a study's dataset or recipe. The last
   two are exactly the ones the database cannot guard (fact 2), which is why this is a command
   with a check and not a `DELETE` statement in a runbook.

5. **There is no `--force`.** The flag would exist for precisely the case clause 4 forbids, and
   its consequence is the one clause 1's context describes as uncorrectable.

6. **A brief is deleted only when it is orphaned** — when no other content references it after
   the deletion (fact 3). Generator lineages and versions are never touched: they are shared by
   construction.

## Consequences

- **Production keeps its property**: nothing removes content there, so a published report can
  never dangle. The property now holds because it is decided, not because nobody wrote the code.
- **The FK map stops being tribal knowledge.** The order, the two cascades and the untyped
  `events.aggregate_id` live in one tested command instead of in whoever last did it by hand.
- **The check is stricter than the schema, permanently.** Two of the six tables it consults have
  no constraint behind them, so the command cannot be replaced by database rules later without
  losing coverage — a note for anyone tempted to add `ON DELETE` clauses and delete the code.
- **The deletion is short precisely because the guard is strict.** Unused content has no
  evaluations, assignments, campaigns or studies to clean up, so what remains is the profile,
  the content, an orphaned brief and their events. Weakening the guard would lengthen the
  deletion, which is the correct incentive.
- **(−) Cleaning a real environment stays impossible**, by design. If that need appears it is
  the retirement conversation, and this ADR is what it supersedes.
- **(−) A local database can drift from production in a way no migration explains.** Acceptable:
  a local database is disposable and `seed-demo --reset` already assumes it.

## Alternatives considered

- **Model retirement in the domain (event, status, policy, endpoint)** → rejected as premature.
  It answers a production question nobody has, and it is the larger change: an aggregate state
  that every consumer of content must then interpret, including the fitness projection and the
  golden dataset.
- **A hard delete available in production** → rejected by fact 1. The report is immutable, so
  the only safe delete is one that can prove no report names the content — and proving it needs
  every study ever published, which is the retirement conversation wearing a delete's clothes.
- **A `--force` escape hatch** → rejected. See clause 5: it exists only for the forbidden case.
- **Raw SQL in a runbook instead of a command** → rejected by fact 2. A runbook cannot enforce
  the two checks the database does not, and the procedure is exactly the kind that fails when
  reconstructed from memory — twice out of three attempts, in the episode that prompted this.
- **Extending `seed-demo --reset` to take a scope** → rejected: `--reset` is deliberately
  wholesale, and its own docstring explains why a scoped reset strands rows. Narrowing it would
  undo that reasoning to serve a different need.

## References

ADR-0008 (local mode implies a local database — the single condition this command's guard
rests on) · ADR-0006 (query ports and Python aggregation — why the study's references carry no
foreign key, which is fact 2) · ADR-0013 (`GenerationBrief` and the paired design — why briefs
are shared, which is fact 3) · ADR-0003 (events-first and the outbox — the model in which
"removal" was simply never written) · ADR-0025 (precedent in form: a decision recorded
precisely because it is deliberately not built) · `docs/design/12-define-qa.md` inv. 3 (the
published report is immutable) · `backend/README.md` §*Registering courses*.
