# STATUS

**The only place in the repo with dated status.** It is **rewritten** whole whenever something
changes; history is not stacked here (that is what git is for). If you find status in any other
document — "already done", "X missing", "N tests green", "verified on such-and-such day" — it is
in the wrong file and belongs here.

_Last updated: 2026-08-24._

## Where we are

**Slice 1 (human MVP): complete and verified locally; the deploy is missing.
Slice 2 (generator QA engine): the first increment is code-complete — 7 of 7 blocks,
plus ADR-0024 (generator declaration + late attribution), ADR-0023 (the fitness
projection the genetic-algorithm experiment reads), ADR-0027 (package intake by
mechanical discovery), ADR-0034 (LLM-carrying assessors, realized by
`drafts-hybrid`, whose v3 takes the first criteria the model itself judges — see below),
ADR-0037 (execution failure is an outcome — realized end to end, see below) and
ADR-0041 (the frozen report is the record, not the reading surface — a study's result
is readable before it is signed, and the evidence behind every criterion lives outside
the frozen row) and ADR-0042 (a judgment names its author, and a study's result is a
triple — dataset × instrument version × assessor, realized end to end) on top of it.**

**ADR-0044 (a study's recipe declares which generators it measures) is decided and its
backend + minimal console are in — see below.**

**ADR-0049 (registering a human evaluator is an invitation, not an account) is decided and
in, end to end.** A human `Assessor` had no act that created it:
the row appeared at the first login with whatever role `ADMIN_EMAILS` gave it, everything
around that decision happened in Clerk's dashboard, and `assessors.expertise` — a column the
GLOSSARY makes part of what a human assessor *is* — had no writer at all. Now an admin
**invites**: `assessor_invitations` records the address, the role, the expertise and who
asked, and the assessor is still born at that address's first login, already carrying them.
The invariant ADR-0007 protects is untouched, because redemption happens **only while
creating** an assessor — an existing one is never re-examined, so authentication still cannot
escalate a privilege — and an invitation is not a principal, which is what keeps ADR-0007's
own refusal ("seeding an admin row by email") standing. Redemption requires a verified
address: matching on one the provider never vouched for is a known account-takeover shape, so
`email_verified` joins the JWT template and a login that would have redeemed without it logs
a warning naming the template rather than failing silently. **`expired` is derived** from
`expires_at` and never stored, so no job exists to keep a status honest; at most one
invitation is pending per address, and revoking frees it again. Delivery is a port with a
**logging adapter**: creating the invitation in Clerk is a separate act until its adapter
lands, and the log says so instead of implying an email went out. In local mode
`GET /dev/identities` offers the invited-but-never-seen addresses — marked `invited` in the
user picker — so the whole flow walks end to end with no accounts and no cloud;
`invite-assessor` and `list-invitations` do the same from the CLI. **The console is
`/admin/assessors`**, where the pending list sits above the registered people because it is
the half with an act on it: invite, re-send, revoke, and `expired` as its own badge beside a
row that still reads `pending` — the two can disagree, and that is the point of deriving it.

**ADR-0050 (granting a role is an act of the console) is decided and in.** ADR-0007 settled a
real property — *authenticating cannot escalate a privilege* — and then, to keep it obviously
true, made `set-role` the only mechanism. The sentence conflated two actors: the invariant is
about the person **signing in**, the restriction about the person **administering**, and
nothing in the first needs the second. In practice it meant one person with production
credentials, at a time that suited them, with no record beyond shell history — and, after
ADR-0049, a roster editable exactly once. `PATCH /admin/assessors/{id}` now grants and
withdraws, refusing the two cases nothing inside the product could undo: **your own row**
(somebody else grants it) and **the last admin** (counted in the store at the moment of the
act, not over a list a page load once read). An automated assessor is refused too — what it
may do is ratification's answer (ADR-0019), and a role control would offer a competing one.
Setting a role somebody already has is a no-op, **not an event**: a change that changed
nothing must not enter the outbox. `AssessorRoleChanged` carries `from`, `to` and `changedBy`,
because the audit question is never "what is their role" but "what changed, and who decided".
The console's role cell is a select except on your own row, where it stays a badge with its
reason next to it. `set-role` survives as **break-glass**, enforcing neither guardrail and
documented as such. Clause 3 of ADR-0007 is superseded; the rest of it stands.

**ADR-0054 (a deployment is declared when it exists, and redeclared when it moves) is decided
and in.** ADR-0028 made the consumable URL optional and wrote down what that cost: *"deploying
an already-registered course means declaring a new version or a hand-written UPDATE."* ADR-0052
§6 turned that cost into a blocker — the campaign judges the deployed, processed course while
the evaluand stays the **draft**, and drafts are registered from `courses/`, which declares no
URL. `register-package --all` refuses `--consumable-url` (one URL cannot declare a deployment
for many), `RegisterContentVersion` was the only writer of `contents`, and re-registering is a
no-op — so **every content the campaign meant to put in front of an expert was unassignable.**

The act is `attribute-generator`'s shape and **parts from it on the one thing that matters:
it may be repeated.** An attribution is a discovery — the fact was always true, so replacing
one would rewrite history — while a deployment is a statement about the world right now. A
course moves, comes down, is redeployed; a declaration that could be made only once would
leave a dead link with no repair, which is the hole being closed, recreated one level up. The
`STATUS.md` sketch that said *"one-way… refusing what is already declared"* inherited the rule
from the wrong precedent, and ADR-0054 §2 says so.

**A change is recorded and a no-op is not.** `ConsumableUrlDeclared` carries `from`, `to` and
who, because the audit question is never *what is this content's URL* — the row answers that —
but what changed and who decided (ADR-0050's rule). Declaring the URL a content already has
writes nothing, records no actor and emits nothing. The update is **conditional on the value
that was read** (`IS NOT DISTINCT FROM`, since the previous value is usually NULL and
`NULL = NULL` is not true), the same trick ADR-0024's `IS NULL` plays: two admins declaring at
once end with one refusal instead of one silent overwrite. **Clearing is refused and named**
rather than left as a silent `null` — a course taken down is a real thing to want to say, and
saying it needs an answer about the evaluations already produced against the old URL that
nothing consumes yet.

**Both gates:** `POST /admin/contents/{id}/consumable-url` and `declare-deployment`, which
takes `--external-id --url` or a `--from-csv` of `external_id,url` read as forgivingly as
`register-package --from-csv` reads its list. Resolution is by slug because what arrives is a
spreadsheet, and two things are refused rather than guessed: the same course named twice with
different URLs, and a slug registered at more than one version — `(format, external_id)` is the
logical content (ADR-0005) and which version is deployed is not something a slug settles. A
failed row makes the run exit non-zero, so a fifty-row file cannot half-succeed quietly.

**And the question it will be asked, answered by a test:** the act **fetches nothing**. A
profile is built from artifact locators and `content_profiling` never reads this field; the
only subscriber to a registry event is auto-profiling, which reacts to
`ContentVersionRegistered`; and that use case refuses coordinates it already profiled. The test
snapshots the profile row, its entry count and the content hash on either side of the
declaration and asserts they are identical.

One thing found while building it and worth keeping: the new use case first defined its own
`ContentNotFound`, and the router went on catching `attribute_generator`'s — two exceptions
with one name, and a 404 that arrived as a 500.

**That is now one class and a rule.** `ContentNotFound` lives in
`evaluand_registry/application/errors.py`, the shape `identity/application/errors.py` had
already set: a module's `errors.py` holds the refusals **more than one act shares**, and an
exception belonging to a single act stays with it. `ARCHITECTURE.md` §3 states it — *one name,
one exception, within a module* — and `test_an_exception_name_means_one_thing_within_a_module`
checks it, resolving exception-ness within each module so local hierarchies count. Across
modules the same name stays legal, because the registry's `ContentNotFound` and Content
Profiling's mean different things and the CLI aliases one of them. The check was verified by
reintroducing the duplicate and watching it name both files, which is the only way to know a
guardrail is not decorative.

**ADR-0053 (an undeclared datum is not asked of a human) is decided and in, and it corrects
ADR-0052 §7.** §7 said an item resting on a datum the course never declared is withheld and
its value produced by the system — right — and then that the derived value *enters the fitness
and penalises*, citing ADR-0023 §2. **Both halves of that sentence are wrong, and the second
would have written a defect into the record that does not exist.** The fitness is the wrong
aggregate: `fitness.py` computes over `criterion_outcomes`, and nothing a rater does has ever
reached it. And the case the feature exists for is not an omission at all — a **LearnpackV1**
package produces **no entry** for `learning_objectives` / `target_audience`, not an `absent`
one, because the V1 adapter declares no capability for them (the format has nowhere to put
them, ADR-0017). `derivation.py` reads that as **`not_applicable`**, which ADR-0023 §2 puts
*out* of the denominator: the automated side does not charge a V1 generator for objectives it
had no field to declare, and neither may the human side.

So the rule has **three branches, in the order `derivation.py` uses them** — capability first,
absence second, because read the other way round a course whose format cannot express
objectives is indistinguishable from one that omitted them. No entry → withheld with **no
score**. An explicit `absent` → withheld at the **scale minimum**, which is what the
penalising outcome looks like on a 1–5 scale. A value → **asked**. And **no `ok` profile means
everything is asked**: an unknown fact is not an absent datum, so a content that was never
profiled, or whose profiling failed, settles nothing.

`criterion_scores.derived` (migration 0026) is ADR-0021's own column ported over, and with a
nullable `score` it yields **four states out of two columns** — a judgement, an abstention, an
item this format cannot declare, an item the course could have declared and did not. No third
column, and no way for the four to disagree. `criteria.required_data` carries the ids an item
is about, under **the same name the automated instrument uses**, because it is the same
demand-side namespace; what differs is the consequence. Four items declare one:
`objectives-observable`, `alignment-coverage` and `alignment-assessment` name
`learning_objectives`, `progression-starting-point` names `target_audience`. **Not
`prerequisites`** — no adapter in the repo declares that capability, so naming it would
withhold that item everywhere for ever, and the rater reads the deployed course, where
prerequisites can sit in prose no profile extracts.

**The rule is one function** (`RubricSnapshot.withheld`), read by the screen to decide what to
ask and by the submit path to decide what to derive. Two definitions could disagree, and the
disagreement would break the `Evaluation` aggregate's exact-coverage invariant at the moment
somebody pressed submit — the same argument ADR-0020 §3 made for the value-domain grammar.
Both callers reach Content Profiling through its published `get_declared_data`, which is where
the `status = 'ok'` guard lives: `get_profile` deliberately falls back to the most recent
*failed* profile so the workbench can show what broke, and a consumer that forgot the guard
would read a broken extraction as a statement about the course. **A client cannot answer a
withheld item**: the router recomputes the set and overrides whatever was sent, because what
an item is worth when nobody was asked is a mechanical fact, and `derived` is absent from the
request model so a judgement cannot be laundered into one.

Reporting excludes derived rows from the average and the dispersion — nobody judged them — and
`CriterionSummary` gains **`withheld`**, because a criterion showing no average for two
different reasons with nothing to tell them apart is the coverage lie ADR-0011 §3 forbids. The
admin table says *not declared* where a dash would have read as "nobody agreed on a number".

**The consequence to know before composing the dataset:** over LearnpackV1 courses the four
objectives-dependent qualities receive **no human data at all** — the rater sees eight items,
not twelve. They are measurable only on contents whose format declares those ids, so the mix
of the campaign decides how well that family of claims can be validated. It is a real loss of
coverage and the honest one: the alternative was a number about a question the course never
answered.

**ADR-0052 (the human reference is elicited per quality) is decided and in.** ADR-0015 gave
the panel a job — *"each claim is correlated with the human score of **its** quality across
the contents of the set"* (§4) — and a shape: five items, one per `PedagogicalDimension`,
1–5 (§3). **The two do not fit.** `course-drafts-qa-v9` carries 21 claims over 19 qualities
and the form produced five numbers, so the four claims of the objectives family could only be
correlated against *the same* one, and the two failure modes the panel exists to separate —
*the criteria measure something else* and *this question is not answerable holistically* —
came back indistinguishable. The per-claim diagnosis was not weak at that grain, it was
arithmetically unavailable. So the reference is now **twelve items, one per `Quality`, with
the item's id equal to the `qualityId`**: after ADR-0026 a claim asserts about exactly one
quality, which makes the join a primary key rather than a mapping. `Rubric v1` is superseded
rather than amended — the stability §3 protects binds *from* the first campaign, and none has
run, so the shape was free exactly once and is now frozen at v2. The response is **agreement
with a statement**, on the same five points for every item, with the behavioural anchors v1
never had moved into each item's `guidance` as an **Agree** half and a **Disagree** half that
each stand alone (a half written as the continuation of the other is not read at all, because
a rater reads one or the other). Twelve anchored items cost a rater less than five unanchored
ones: the scale is learned once. **The bottom of the scale is an answer and the abstention is
off it** — `1` means *the course does not do this* and has to weigh like the absence-derived
`fail` (ADR-0021), while *"I couldn't see enough of this course to judge"* is a null score
(migration 0025 drops the NOT NULL; the 1–5 CHECK is left alone, since a null passes it) and
is averaged into nothing. The twelve were chosen where validity is at risk rather than where
evidence is abundant, and deliberately include the three this repo had already written down
as unresolved: `progression-cognitive-demand` (`MEASUREMENT.md`: *"a proxy awaiting
calibration against the human reference"*), `coherence-reinforcement` (ADR-0047 §8's bar,
*"underspecified and known to be"*) and `progression-prerequisites` (zero violations over
three drafts against a defect two independent readers found). The panel reads the **processed,
deployed course**, declared as the draft's `consumable_url`: the evaluand stays the draft, so
the two sides meet on one `contentId` with no join, the prose is the same text, and only the
assessment item is confounded — the human read a delivered challenge where the instrument read
a proposal (ADR-0046), which the ADR names as an alternative explanation instead of hiding.

**ADR-0051 (an assessor leaves without being erased) is decided and in.** Nothing removed a
person from the roster: they appeared at their first login and stayed for ever, in every
picker and — the half that matters — able to sign in. Just-in-time provisioning is the
arrival and nothing else; nobody stops existing by not signing in. Deleting the row was never
the alternative: an `Assessor` is the key of provenance, one third of the triple that
identifies a result (ADR-0042), and every `CriterionScore` names its author — the argument
ADR-0033 already made for content, with more force. So leaving is `assessors.status`
(migration 0023), and **the refusal lives in `get_current_assessor`**, the one place a request
becomes an identity: a status that merely dropped somebody from pickers would be cosmetic
while their credential still opened everything. The two guardrails are ADR-0050's — not
yourself, not the last admin — and `count_admins()` now counts **active** admins, so the
guard protects a door somebody can actually open and ADR-0050's own refusal reads correctly.
An automated assessor is refused: it is withdrawn by ceasing to declare it in code. The
assign picker drops deactivated people outright rather than disabling them with a reason
(ADR-0028's idiom is for facts somebody can fix); the roster keeps the row, dimmed and
labelled, because "what happened to them" is a question that page exists to answer. **Not
done, deliberately:** deactivating does not cancel open assignments — that is an
orchestration act with its own aggregate, and reaching into it from an identity act would
cross the boundary the wrong way.

**And the credential stopped naming its vendor.** `assessors.clerk_user_id` put Clerk inside
the pure domain, and it had already stopped being true: ADR-0008 added a second adapter, so
local mode was storing `local|<email>` in a column called `clerk_`. Migration 0024 splits it
into `(auth_provider, auth_subject)`, unique together — which is what the `local|` prefix was
standing in for, so the prefix goes and a local subject is now just the address.
`get_by_clerk_user_id` becomes `get_by_credential(provider, subject)`, `ClerkIdentity` becomes
`ExternalIdentity`, and `security.py` fills the provider from `AUTH_MODE`. **No ADR: nothing
was decided.** ADR-0004 and ADR-0008 stand exactly as written; this makes the second adapter
they already introduced honest in the schema. The backfill states what each row was —
`local|`-prefixed came from the local adapter, everything else from Clerk — rather than
guessing, because both adapters wrote through the one lookup and there was no third source.

**And the expertise profile finally has a reader.** ADR-0049 justified the field by giving it
a writer; it got one and had none on the other side — `AssessorDTO` did not carry it, the
roster endpoint did not publish it, and the console showed it only while the invitation was
still pending, so it vanished the moment the person signed in. It is published now and shown
in two places: under the name in the roster, and **in the assign picker's option label**,
which is the act it exists for — deciding who should read this course.

**And it can be corrected.** Invitation time is the only moment anybody knows the profile, and
also the only moment it is guaranteed true: people change what they work on, and everybody who
signed in before invitations existed carries nothing. `PATCH /admin/assessors/{id}/expertise`
edits it, from the profile line itself in the roster — that line *is* the control now, and
reads *Add expertise* when there is none. **It carries none of the roster guardrails, on
purpose**: a role and a deactivation decide what somebody may do, so both refuse the changes
nothing could undo (ADR-0050, ADR-0051); a profile decides nothing, so you may correct your own
and a deactivated assessor's alike. Blank clears it — an empty box and an unfilled one say the
same thing. Still an event (`AssessorExpertiseChanged`), because somebody typed it and later
somebody may want to know who. **No ADR: nothing decided ever said the profile is write-once.**

**And long profiles are handled where the space is fixed.** A native `<option>` carries no
width and no styling of its own, so a long profile pushed the evaluator's name out of view.
The label now shortens it at a word boundary with an ellipsis, and the **whole** profile of
whoever is selected is shown under the control, where it has room.

**And inviting is one act again.** ADR-0049 left delivery as a port with a logging adapter,
which meant an admin invited here *and* in Clerk. `ClerkInvitationDispatcher` closes it:
under `AUTH_MODE=clerk` with a secret key set, inviting creates the Clerk invitation too, so
the person gets the email and can sign in to an invite-only instance. The adapter is chosen
by **auth mode** — the seam ADR-0008 already draws — so a local box still delivers nothing
and says so, and the whole flow keeps running with no accounts and no cloud. Two details are
decisions rather than defaults: `ignore_existing` is **on**, because Clerk refuses a second
invitation for an address that already has one and re-sending is exactly that case; and
`expires_in_days` is derived from our own window, because Clerk's default is 30 days against
our 7 and two expiry dates for one invitation is a support question waiting to happen.
**Delivery can fail without the invitation failing** — an address that is already a Clerk
user is refused and cannot be bypassed — so the act commits first and then reports:
`delivered` and `delivery_error` carry Clerk's own sentence on the two endpoints that
deliver, and are null on a listing, because whether an email got out days ago is not a fact
the row carries. A `clerk` process with no secret key falls back to logging with a warning
rather than failing every invitation. **No ADR: ADR-0049 §8 named this adapter as the thing
that was missing; this is it.**

**The link it sends now lands on a page that can finish the job.** The first real invitation
went out pointing at `/sign-in`, and the person accepting it got Clerk's card with a spinner
that never resolved. The reason is structural, not a bug in the card: somebody accepting an
invitation **has no account yet**, so Clerk hands the ticket over as `__clerk_status=sign_up`,
and `<SignIn/>` cannot complete a sign-up ticket. `/accept-invitation` is the second public
route — a catch-all, because Clerk's component owns the sub-paths of its own multi-step flow
— and it renders `<SignUp/>` through the same seam every other auth surface goes through, so
the page still imports no Clerk in local mode. The default `redirect_url` moved with it. **The
redirect URL is baked into the ticket when the invitation is created**, so links sent before
this keep pointing at the old page: revoke and invite again.

**Then the first real redemption did not happen, quietly**, which is the failure ADR-0049 §3
predicted and this closes on three fronts. The person signed up, appeared in the roster with
the default role, and their invitation went on saying `pending` — no `InvitationAccepted`
anywhere. Two causes, one documentation and one code. **The JWT template shortcode this repo
documented does not exist**: it is `{{user.email_verified}}`, and the invented name meant the
claim never arrived, so the gate refused every redemption exactly as designed. And **the gate
read the claim wrongly**: Clerk interpolates a *quoted* shortcode into a string, so the claim
is legitimately `"false"` — and `bool("false")` is `True`, which would have turned an
unverified address into a verified one, the precise thing the gate exists to prevent. It now
accepts a real boolean and the string `"true"`, reads `"false"` as false, and treats anything
it cannot interpret as unverified. Third front, because a quiet failure needs a loud symptom:
the console now marks a pending invitation whose address **has already signed in** as one
that can never be redeemed, naming the likely cause and the two remedies. Nothing recovers a
redemption after the fact, by design — an invitation is consumed while the assessor is being
created and never afterwards, which is what keeps a login from escalating a privilege.

**And a crossed auth mode now says so.** The two halves of ADR-0008's seam are configured
separately — `AUTH_MODE` in the backend's environment, `NEXT_PUBLIC_AUTH_MODE` in the
frontend's — so they can disagree, and when they do **every** request is a 401. The message
was `missing bearer token`, which sends a reader looking for an expired session; nothing is
wrong with the session, the two sides are not the same app. The evidence was in the request
all along: a caller built for the other mode sends the other mode's credential. So the
mismatch is named — which mode this API runs in, which credential arrived, both files to
change, and that neither value is re-read while running. A request carrying nothing at all
still gets the ordinary "missing credential", because saying "check your auth modes" there
would be a guess. The root `README.md` gains the six-line version of the same thing: the rule
was documented once, half of it, in `frontend/README.md`.

**ADR-0043 (choosing is not pinning, and publishing is signing off) is decided and being
built in three steps.** Step 1 is in: a study carries a `name` and an optional
`description` (`purpose` goes back to meaning the typology the GLOSSARY reserves it for),
and the act that closes a round is a **signature** — `signed_off` in the status, in both
columns, in the event and in the console. Report `SCHEMA_VERSION` is 3; migration `0020`
deleted every frozen report, once, under clause 11 — the last moment that was free of
cost, and the clause says so. Step 2 is in too: a draft's instrument, judge and briefs
**replace freely** until `open`, which is now what pins them — `POST /admin/studies` takes
the whole selection and `PATCH /admin/studies/{id}` corrects it, where three pin/compose
endpoints used to be; `InstrumentPinned` and `AssessorPinned` are retired because
`StudyOpened` already carries the triple. Step 3 closes it: the four setup steps and the
"new study" dialog are gone, replaced by **one form** (`components/admin/study-form.tsx`)
that serves `/admin/studies/new` and a draft's own page alike, filters judges by
ratification, marks courses whose format the instrument can only read in part instead of
hiding them, and whose primary action — *Save & evaluate* — saves, opens and starts the
batch in three requests, so a failure in the middle leaves a valid draft.

**And the recipe now names generator versions (ADR-0044), which closes a defect that was
producing mixed results in silence.** A study's recipe was briefs alone and the
materialization was literal — every content registered from those briefs, whatever made it
— so a round meaning to measure one generator version measured every version that had
answered the same commission, which is the ordinary case and not an edge one: a brief is
handed to a new version precisely when somebody wants to know whether the new version is
better. Now the recipe has a second axis, `generator_scope`, in **one field with two forms**
— `"all"`, or a non-empty list of versions — so "every version" is something a person says
rather than what the absence of a filter means. It is **required**: `open()` refuses a study
that never declared it, beside the instrument and the judge, and `prepared` waits for it.
How many versions it names is what makes the round a measurement (one) or a comparison
(several) — which is why **`purpose` still is not built**: a second field would be a label
that can disagree with its own dataset, the defect ADR-0043 §8 removed from this screen.
The comparison is read where optimization is read (the fitness projection's per-version
grain, ADR-0023), so nothing was added to the frozen document and `SCHEMA_VERSION` did not
move. Migration `0021` adds the column **nullable with no default** — null is a draft that
has not declared, and a surviving default would let an insert that forgets the field mean
"all" silently — and backfills every existing study to `"all"`, which states what those rows
already did rather than guessing what they meant. **The CLI contract broke on purpose:**
`declare-study` and `update-study` take `--all-generator-versions` or repeated
`--generator-version-id`, and a study that never passes one cannot open — the GA scripts
have to name a scope. The console asks for it as a required field between the judge and the
courses, and narrows the course counts to the versions ticked so the number on screen is the
number that will run.

**The form then learned to show the comparison, which is the half a person acts on.** Once a
round measures more than one version, each brief row carries a count **per version** — the
zeros included, because a commission that answered one version and not another is the
unpaired A/B that nobody would otherwise notice until the numbers were read (the shape
ADR-0039 settled for the report, applied where it can still be fixed). Three warnings sit
under the list, all of them informing and none blocking (12-define invariant 1): commissions
missing from some arm · **arms whose coverage differs**, which is ADR-0023 §7 said where it
is actionable — two versions leaving a different number of criteria unassessed have
different denominators, so their values are each correct and their difference is not · and,
under *Every version*, the plain statement that the round pools the versions the briefs
brought and its header reads them as one population. The summary line and the confirmation
dialog name the scope in the same clause (*comparing 2 generator versions*, with the count
per version), so the last screen before the irreversible act says what the round is.
**Deliberately not refused:** the cross-format A/B, which is exactly the change worth
measuring when a generator changes its output format (ADR-0044 §7).

**And the comparison is now legible where it belongs — the fitness projection, not the
report.** ADR-0023 built the per-generator-version grain as an optimization signal and kept
it out of `study_reports`; that is where two versions are compared, so this changed nothing
frozen and `SCHEMA_VERSION` did not move. `FITNESS_FORMULA_VERSION` stays `"1"` too: no
state entered or left a denominator. Each generator section now carries **its own coverage**
(`notAssessed`, `executionErrors`), which is what makes ADR-0023 §7's equal-coverage rule
checkable at this grain instead of merely stated — two versions can both read 1.00 and have
been measured over a different number of criteria, and before this nothing on the page could
say so. One `_coverage` helper serves the study grain and the version grain, so the total
and its parts cannot drift into counting different things. The console renders the versions
**side by side** — one column each, one row per dimension, with courses/unassessed/errors
under them — instead of the sequence of separate tables it used to be, plus the amber band
when the columns' coverage differs and a line pointing at *By brief* first: a gap between
two columns only means something if it is larger than how much one version varies with
itself on the same commission (ADR-0039). The matrix renders only from two versions up; with
one, a single-column comparison would dress a measurement up as something it is not.

**And the CLI finally reads the tree the generator actually writes into.** ADR-0035 gave the
console declared source roots and recorded, as its own deferral, that the CLI stayed on
`courses/` alone — which is the tree nobody's generator writes to. `register-package` now takes
`--root <key>` (default the built-in `courses`), resolving through the same
`local_sources` module the console reads, so the two cannot answer differently about what is
readable or about the locator a package registers with; a `--source` that is not a URL is read
from where you stand and then, if that names nothing, relative to the root. An undeclared key is
refused before anything is read, naming **both** ways that happens — never declared, or declared
after the API started, since the trees are mounted when the app assembles.
**The generator folder gained its second convention and its one automatic act.** A generator
that names its own output folder writes `<name>-<version>` (`learnpack-generator-04a7dd5-dirty`),
which cannot be split on its separator because the version carries hyphens too — so it is split
against the registry: the registered lineage whose name the folder starts with, longest match
wins, and the rest is the version. `courses/`'s `<name>@<version>` is tried first and is
untouched. A **version** that is new is now registered as it is read, and printed as it happens;
a **lineage** never is. That asymmetry is the decision: a version is a fact about a run and
changes with every commit of the generator being measured, while a lineage's name is typed once
and never again (ADR-0031 guards it with `--distinct-from`), so demanding a second command per
version would put a manual act inside the loop this intake exists to automate. **No ADR:** ADR-0035
listed `--root` among its deferrals and rejected the shared-resolution refactor with the
condition attached — *"the refactor becomes worthwhile only if the CLI grows `--root`"* — which
is what this is; the folder convention is ADR-0027 §5's, and both of its readings still refuse
to mint a generator identity (ADR-0024).

**And a fresh database is now a working one (ADR-0045).** Migrating and seeding left a store
that held no published instrument, vouched for no adapter and permitted no assessor to judge —
so `evaluate` refused and `/admin/assessors` listed three packages with no row behind them. The
ten commands that fixed that were a runbook, which is a list whose order matters and whose
version ids must be typed right; the failure it produces is a store that looks set up and
measures with a norm nobody chose. **`seed-workbench` replays them from
`docs/seed/workbench.yaml`** — instrument versions to publish, formats whose extraction is
accepted, generator lineages to register — under the local-mode gate and attributed to the
local admin. What is replayed is the **repetition, never the decision**: it installs exactly
what the manifest names and passes no `--confirm` to a ratification, so a changed executed
criterion still stops it (ADR-0019). **Assessors are deliberately not in the manifest**: which
ones exist is the code registry's answer (ADR-0016), so every package is ratified against the
published version of its own lineage — one version per lineage, two refused rather than
resolved — and adding a package needs no edit there to become usable. Idempotent **by asking
rather than by swallowing**, since a swallowed refusal would also hide ADR-0031's near-miss
guard firing on a real typo. `task setup` runs it and no longer runs `seed-demo`, which stays
as its own command (and `task seed:demo`) because the human MVP's two courses and campaign are
not an operator's data; **`task db:reset`** destroys the volume and rebuilds the whole thing,
the volume rather than a list of tables because a wipe that enumerates is a wipe that forgets
the table added last week. Two instrument drafts nothing reads — `course-drafts-qa` v3 and v4 —
were deleted with it, and v1, v2, v5, v6 and v7 followed when v9 landed (see below) — the
lineage on disk is v8 and v9, and the assessor coverage tests glob it instead of naming
versions.

**And one command now takes a generation from the folder to the score.** Measuring what the
generator just wrote was `register-package --all` → `declare-study` → `update-study` →
`open-study` → `evaluate-study` → `show-fitness`, six commands with four ids copied between
them, which is the pendiente the collaborator's handover was blocked on. **`measure --root
<key> --path <folder>`** chains them and derives the ids. Nothing new happens inside it: the
folder's name declares the generator version and that version — one, not "all of them" — is
the round's scope (ADR-0044), which is the defect the chaining removes rather than the typing.
The norm is the published instrument bound to the format and the judge is the assessor that
ratified it, **derived only when the derivation has one answer** and otherwise asking for
`--instrument-version-id` or `--assessor` (which takes `name` or `name:version`, so a daily
loop needs no editing on a bump). Both are resolved **before** the folder is registered:
registering is a fetch per lesson per course and profiles each one, and none of that is worth
doing for a round with nothing to judge it with — the ADR-0040 stance, applied one level up.
Re-running **resumes** rather than declaring a second round: an open study with the same name,
norm, judge and dataset is continued, and anything less than an identical match is a new one.
Out comes **one** JSON document, `{batch, fitness}`, because reading the run and the score
separately is where a value gets paired with the wrong round. A folder declaring `unknown` is
refused — a round's scope is which versions it measures, and "none" is not a version.
`evaluate-study` and `show-fitness` are unchanged; both now print what `measure` composes.
**One consequence is worth knowing before the first run:** a course keeps the generator
version it was first registered with, since a re-registration returns the existing course and
discards the declared generator (ADR-0035 §9) — so a store that already holds a generation
under another version measures it there, and `measure` names each such course instead of
composing an empty dataset. Measured against the real tree, every generation in it is already
registered under one version, which is the mixed population ADR-0044 was written about;
`task db:reset` and one `measure` per folder is the clean start.

**And what a draft PROPOSES to be assessed on is going to count (ADR-0046), in three steps of
which this is the first.** The drafts lineage was judging assessment through half of what a
draft offers: LearnpackV2 emits an exercise as a *proposal* inside the lesson body, the adapter
excluded those on purpose, and `lesson_assessment_items` therefore collected only what ships
ready for the learner. Over the five drafts on hand that is 5, 8, 10, 14 and 14 proposed
exercises against 5, 12, 3, 3 and 3 delivered items — and **the five objectives repeated
judging reported as measured by nothing are covered by proposals**, several near-verbatim
against the objective's own declared verification. So `cr-every-objective-has-an-assessment-item`
was failing as an artifact of the extraction, and the systematic failure of
`cr-assessment-matches-the-declared-verification` (*declared verifications ask for production,
items ask for recognition*) does not weaken but **reverses**: the proposals are the production.
ADR-0046 admits them as evidence for the alignment claims and mints **one** id carrying the
whole surface with every entry marked `delivered` or `proposed` — one list rather than two
because a criterion is silent when any datum it requires is absent, and three of the five drafts
are a single question block away from being all-proposals. It landed in three steps.
`course-drafts-qa` **v7** mints `assessment_offerings`, re-points its three assessment criteria
at it — each saying in its own words which of the two kinds it counts — and widens the claim's
statement from *the assessment items the draft carries* to *the assessment the draft offers*.
The **LearnpackV2 adapter v3** supplies it: the delivered half is the same reading
`lesson_assessment_items` reports (a test pins that the two can never disagree about a
question), and a proposal's prompt is the fence's own text, because inside a `question` fence
the author writes the expected answers while a proposal fence holds the instruction itself.
And **`drafts-hybrid` v11** reads it: one index space over both kinds with every entry marked,
separated by blank lines because a proposal's prompt runs over several lines and the old
one-line-per-item layout would have let one task read as several; two rewritten extraction
prompts that say what a proposal is; and a new metric,
`objectives_measured_by_proposal_only`, beside the count of what was offered of each kind.

**Publishing v7 needed the same human act every version does.** The instrument is a **draft**
until someone publishes it; `seed-workbench` does that from `workbench.yaml` and ratifies the
current `drafts-hybrid` against whatever it names, on a fresh database. On a store that already
published an earlier version, publishing a new one leaves the lineage with **two** published
versions, and `measure` refuses to guess between them — pass `--instrument-version-id` explicitly
or start from `task db:reset`, which is wanted anyway whenever the adapter version also moved:
every content of that format needs `accept-extraction` and a re-profile before anything reads
the new id.

**And a second calibration dump asks the same corpus by concept rather than by lesson.**
`dump-concept-map --content-id <uuid> [--shape whole|per_module|two_phase]` reports, per
concept, the lessons that state it, develop it, use it as known, check it, or merely name it —
with a verbatim quote each. Two properties are what it is for. **The plan's own
concept-to-lesson assignment is never shown to the model**: it gets bare names, works out from
the text where each is stated, and the assignment is joined back on afterwards, so a `defines`
row the plan does not declare is the plan and the prose disagreeing about where a concept is
taught. And **every group is a local act** — `defines` asks only whether a lesson says what a
concept is, never which lesson introduces it; `min(position)` decides that here, so a concept
stated by two lessons is a finding (the course stating again what it already stated) rather
than a contradiction to resolve in a prompt. A lesson may sit in more than one group for one
concept, which was measured: forcing one slot collapses `develops` to almost nothing.
`dump-concept-touches` stays for the one thing this does not produce — the geometry of a
single touch, how far back it reaches and where in the lesson it sits, which is what tells you
whether a pairwise or windowed criterion could catch what a course actually has. Neither is
identity (ADR-0034): no executor imports them, `SOURCE_CONFIG` names neither, their prompts
stay out of the fingerprinted templates, and tests pin that in both directions.

**The calibration material moved out of `backend/README.md` into
`docs/RUNBOOK-calibrating.md`.** Reading a trace, what repeats tell you and the two dumps are
one job with one audience — someone deciding what an instrument should ask — and the repo
already had the shape for that in `RUNBOOK-measuring.md`. The backend README keeps a pointer;
`docs/README.md` gained a runbooks section naming both, which it had been missing for the
measuring one too.

**`course-drafts-qa` v9 splits the revisiting claim in two (ADR-0047), and it is the version
the workbench publishes.**
`cl-course-revisits-what-it-taught` asked whether a course revisits its earlier content, and a
draft answers that twice with different answers: four independent readers of one draft, each
asked unprompted whether it builds on itself, each answered *"partially"* and each split the
same way — cumulative inside a module, rhetorical between them. The mechanical half is what
settles it: a module's opening lesson has no earlier lesson WITHIN its module to build on, so
one ratio over all core lessons averages two populations whose denominators mean different
things, and the lessons that failed on the draft measured were precisely the module openers.
So `cl-modules-build-within-themselves` and `cl-course-builds-across-modules` replace it, both
keeping the quality and warrant of the claim they replace (ADR-0026 constrains a claim to one
quality, not a quality to one claim). `cr-assessment-retrieves-earlier-taught-material` moves
to the across-modules claim **without a word changed** — its pass condition already said
"outside their own module" — and `cr-later-lessons-apply-earlier-concepts` becomes
`cr-lessons-build-within-their-module` and `cr-modules-build-on-earlier-modules`. Both are
**abstained** by `drafts-hybrid` and by `drafts-structural`, with the reason stated: the
concept map is no longer the obstacle, but what a lesson DOES with a concept is not measured
stably enough to decide a verdict — over one draft, two readers found the working-with act in
23 and 29 places while six model runs found it in 0 to 9. The two new criteria therefore widen
what counts: developing a concept, operating with it, or setting a task on it. Naming it does
not count, and neither does saying again what it is, which is a course starting over.
`workbench.yaml` now names v9, so a fresh database publishes it and both assessor packages are
ratified against it — the two new criteria are on the abstained side of the delta, so the
ratification needs no confirmation. **ADR-0047 records the decision** — why two answers about
one quality are two claims, why the bar is wide, and what it does not settle — and the field
runs it rests on are frozen in `docs/design/research/concept-continuity-field-runs.md`.
**`drafts-hybrid` v13 executes the two new criteria, over one concept map the pair shares.**
The abstention named two obstacles and only one was still there: the map itself is fine — two
independent readers agree with it about where each concept is stated — and what was missing was
a measure of what a lesson DOES with a concept that a verdict can rest on. ADR-0047 settles
that with the wide bar, and the executor adds the deterministic anchor: which appearance of a
concept is its INTRODUCTION is `min(position)`, computed in code and never asked. The map is
asked in two passes — definitions over the whole course, usage module by module — which costs
`1 + one call per module` and takes an evaluation from ~15 calls to 22 on the drafts measured.
It pins its own model, effort and output budget, all three declared in `SOURCE_CONFIG`: the
flash model the rest of the package uses does not hold this output contract.
Those calls **go out together**, which is what makes the criterion runnable over a dataset
rather than merely demonstrable: serially the map was 84 % of an evaluation's wall clock — 517
seconds against 97 for everything else — and the same draft now finishes in 321 seconds instead
of 614, returning the identical map. Two things had to be fixed for that to be honest as well as
fast: the trace sink is a `ContextVar`, so the first fan-out emitted nothing at all and the most
expensive task left no record, and the JSONL sink now serializes its writes.

**And the transport's ceiling was still sized for a world without fan-out**, so three of the
seven calls sat in our own queue — which `latency_ms` counts as latency, because the clock
starts before the slot is asked for, so the wait read like a slow model. It was not: at a
ceiling of seven all seven calls generated at 106–134 tokens per second, where at four the
three that queued recorded 46–71 and nothing else changed. `LLM_MAX_CONCURRENCY` is now **8**
— one course's map is one call plus one per module, seven on the drafts measured — and the map
stage went 204 s → 114 s, the evaluation 321 s → 283 s. The number comes from our own demand
because the endpoint declares none: OpenRouter publishes rate limits only for `:free` variants
and governs capacity per account. **How many COURSES a batch runs at once is now its own
setting** (`BATCH_MAX_COURSES`, 4): it used to default to the transport's ceiling, which stopped
making sense when one course became several requests — one is bounded by the database pool, the
other by what the account is served.

**And then the derivation stopped looking at its criteria one at a time (ADR-0048), which took
an evaluation from 283 s to 149 s** — same verdicts, same map, no 429 and no retry. What made
that a decision rather than a patch is where the concurrency went. The obvious repair is a
thread pool inside `derivation.py`, and the line that gives it away is `copy_context()`: a
worker starts with an empty context, and what a run carries there — the assessor's memoized
answers, the trace sink, the cancellation token — belongs to layers the domain must not know
about. So the domain **declares** that its criteria are independent and asks for the answers in
order; the mechanism is injected, its default is sequential, and the concurrent implementation
lives in `platform/concurrency.py` beside the things it has to carry. The domain gained no
import it did not have and its twenty derivation tests run unchanged. Two costs are real and
stated in the ADR: a run past its failure budget now pays for the calls already in flight, and
per-call throughput dips when more is in flight (96–125 tokens per second against 106–134).
`drafts-hybrid` needed one thing to be safe under it — a memo entry claimed **before** the work
starts, so two criteria sharing a task no longer both find it missing and both pay — and
`LLM_MAX_CONCURRENCY` moved to **16**, since a course's peak is now its map alongside the judged
criteria and the single-call tasks.

**The last lever on the map was measured and rejected, and that is where the work on speed
stops.** What sets the floor now is one call generating some thirteen thousand tokens, most of
them reasoning, so the obvious move was to ask the six USAGE passes — three quarters of the
map's output tokens — for less of it. Four runs over the two calibrated drafts say no, in two
ways that look nothing alike. The **same model at medium** got every verdict right and spent
the safety margin: the draft two readers call cumulative went from 8 of 9 to exactly 6 of 9
against a bar of 6, on a quantity known to move (54 and 59 usage rows at identical settings), so
one lesson fewer flips a course that should pass. A **cheaper flash model at medium** broke it
outright — that draft's across-modules verdict went 5/5 to 3/5, both drafts came back with the
same pair, and the criterion stopped telling them apart; it also spent MORE output tokens than
the strong model at medium for a third of the rows. So neither shipped: both passes stay at
`high` and `drafts-hybrid` stays at **13**. The durable half of that is in
`docs/RUNBOOK-calibrating.md` — test a cheaper reading on the draft that should PASS and read
the distance to the bar, because checking that the bad draft still fails is the check a recall
collapse survives for the wrong reason.

**So what is left for a population is throughput, not latency, and a first real batch says how
much.** An evaluation is 149 s and its floor is a single model's single answer, so what scales
is `evaluate-study`, which runs courses at a time against the transport's one ceiling. Six
courses at the defaults — four at a time, sixteen requests in flight — took **304 s against
963 s of course time, a 3.2× on four workers**, with 142 calls, no retry, no 429 and nothing cut
at the budget. **The queueing that was expected did not happen**: four courses peak at a
theoretical 64 requests against a ceiling of 16, but their peaks do not coincide, and the map's
calls generated at 97–139 tokens per second — the same band a single course produces alone. So
the effective figure to plan a generation with is about **50 s per course**, and the knob with
room left is `BATCH_MAX_COURSES` rather than the ceiling: the requests are not saturated, and
what bounds the workers is the database pool at roughly seven.

**That knob was then turned, and it is now 6.** The same six courses run all at once took
**180 s against 954 s of course time — 5.3× where four workers gave 3.2×**, again with no
retry, no 429 and the map's calls generating at 97–141 tokens per second either way, which is
the band one course produces on its own. So a generation plans at about **30 s per course**.
The default stops at six rather than seven because seven is the pool's exact edge: a worker
holds two sessions — its own and the one the policy opens on commit (ADR-0003) — so fifteen
connections reach seven with one to spare, and **a pool that runs out does not slow a batch, it
ends it**, since a failure nobody named stops the whole run. `DB_POOL_SIZE` and
`DB_MAX_OVERFLOW` are settings now, at the values SQLAlchemy was already using, so raising the
two together is a configuration change rather than a code edit; `backend/README.md` carries the
arithmetic, what to measure to know it helped, and what the failure looks like.

**Measured against the draft the readers read**, and it is the strongest agreement this
lineage has: on the SOLID draft of `learnpack-generator-a154586`, both criteria return exactly
what annotators K and L returned — `cl-modules-build-within-themselves` PASS (readers 5 of 6
and 5 of 6) and `cl-course-builds-across-modules` FAIL (readers 1 of 4 and 2 of 4). That is the
"partially" both readers wrote in prose, split into the two findings the claim used to average.
The seven map calls were all answered on the first attempt — no schema retry, no budget cut —
and reported 109 rows against the readers' 117 and 103. The same split shows on a later
generation of the same course and on a prompt-engineering draft, which the readers never saw.
`cr-later-lessons-apply-earlier-concepts` stays abstained: v9 retires it, v8 declares it, and
coverage is a superset of the lineage.

**v9 is the first revision of this lineage to RETIRE a criterion id, and that changed an
invariant.** Until now revisions only added ids or reworded conditions, so "an assessor
declares exactly the shipped instrument's criteria" and "an assessor declares every criterion
of every version" were the same set, and both assessor packages asserted the first. With an id
retired they diverge, and the artifact has to keep deciding the retired one or it stops being
able to ratify v8. Coverage is therefore a **superset** of each version, with a second test
closing the other side — an id decided by an artifact that no version of the lineage declares
is refused, so `declared` cannot silently accumulate retired ids and typos. **v1, v2, v5, v6
and v7 were deleted** in the same change: every study measured so far is development-phase and
disposable, and keeping five versions alive to preserve ratifiability for studies nobody will
read is the tail wagging the dog. v8 stays as the state before this work. One cost is real and
unfixable: ADR-0046 cites `course-drafts-qa-v7.yaml` by path, ADRs are immutable, and that
reference now dangles.

**And the field verification has not been run.** Two questions, both answerable with the three
drafts already on hand: whether `cr-every-objective-has-an-assessment-item` stops failing where
a proposal covers the objective (five of them do), and whether
`cr-assessment-matches-the-declared-verification` still discriminates — the proposals are
written by the same pipeline as the objectives, so alignment between them may be partly
tautological, and the honest test is the same drafts judged by `:10` and `:11` and the two
results compared. Until that is read, the campaign is code, not a finding. One thing is certain
already: the fitness denominator for this lineage moved, so values from before and after are
not comparable (ADR-0023 §7).

**The first six repeats of v11 found the verification criterion unstable, and `drafts-hybrid`
v12 is two thirds of the answer.** Same course, same instrument, same assessor, six runs: one
dead, four fail, one pass — and `assessment_verification_match` spent **21 calls on 6 verdicts,
9 of them retries**. The traces separate three causes, and the two that are ours are fixed.
**The corpus this package builds is a template**, so a model asked to copy a line out of twenty
near-identical ones spliced the prefix of one task onto the body of another; the grounding
check refused it correctly and the retries never converged — 8 calls, no result. The judge now
cites tasks **by number** (the closed-set rule `assessment_reach` has used since v3) and the
passage a report shows is fetched from the profile, which is the course's own text instead of
our label around it — ADR-0009 more exactly, not less. The mapping loses its quote for the same
reason: it is the field that killed a run in the previous campaign. **And one verdict over four
objectives made the model do the arithmetic** — one sample wrote *"satisfied except obj-3"* and
voted pass, while others agreed on a failure naming different objectives. The judge now answers
**one entry per objective** and the criterion is the conjunction, computed in code; the vote is
unchanged, and `verification_failed_by_sample` records which objectives each sample failed, so
a disagreement about the facts is legible apart from a disagreement about the bar. Riding
along: `locate` now ignores a **list marker** the way it already ignored emphasis, which is
what `outcomes_extraction` had been spending 7 retries in 13 calls on.

**Ten field runs measured it, and the first five found a regression this branch had just
introduced.** Dropping a list marker only where the source has it — at the start of a line —
merely turned the false negative around: a model that copied the ordinal faithfully became the
one refused, and `closing_integrates` spent 9 retries in 5 runs on it. The marker is now
invisible wherever a break puts it, on both sides of the comparison. The same runs exposed
something older: **`outcomes_extraction` never used the grounding rule at all**, comparing
bytes against the lesson body while every other citation went through `locate` — which is why
it has always been the most retried task in the package. The rule now lives in `grounding.py`,
shared by both halves. And an index a model serializes as `"0"` is read as `0`: two runs met an
upstream that quotes its integers and one died on it, spending its attempts fixing the type and
then dropping an entry of the twenty.

**What the last five runs measure.** Retries across the whole evaluation: **20 → 7**.
`assessment_verification_match`: **10 calls for 5 verdicts and zero retries** across all ten
v12 runs, against 21 calls for 6 verdicts with 9 retries under v11 — and no run died.
`closing_integrates` 9 → 0, `assessment_reach` 2 retries and a death → 0. The verdict is
**fail in 5 of 5**, where v11 gave one death, four fails and a pass. The two rejections that
remain are the check doing its job: the model reworded a sentence and capitalized a fragment.

**And the per-objective data says exactly where the instrument is under-specified**, which is
what it was added for. Over ten samples: **obj-2 fails 10/10 and obj-3 fails 9/10** — stable
findings about the draft, both of them compound verifications whose tasks cover part of what
they name. **obj-1 fails 3/10 and obj-4 4/10**, and every one of those flips arrives inside a
sample that failed *all four at once* — a wholesale reading that nothing proposed measures
anything, which the pass condition says is wrong and the judge keeps reaching for anyway. The
failure mode splits the same way (0 and 1 for the same objective across runs), because neither
declared mode names what the judge is actually seeing.

**The third cause is the instrument's and was deliberately left alone.** The declared
verifications are compound — *create a directory structure, copy files, rename a file, remove a
directory* — and nothing says whether covering the kind of performance is enough or every named
element must be asked for; the repeats split exactly there, and the failure mode the judge kept
reaching for does not name what it was seeing (partial coverage). That is a **future
`course-drafts-qa` revision** with a threshold and a third failure mode, and it goes after
v12's field runs, because moving the mechanism and the bar in the same round leaves the next
campaign unable to say which did what. The other open one, older: **the provider is not
pinned** — six runs drew seven upstreams, with answer lengths from 294 to 1184 tokens and
latencies from 3.5 s to 56 s for the same question, which is ADR-0034 §3's known gap now with
evidence attached.

**The generator renamed a declared field, and the chain that follows a package format change
went through once more.** `files/lesson_plan.json`'s per-lesson `concept_covered: str` became
`concepts_covered: list[str]` (plus an unrelated `lesson_focus` no criterion consumes, so it
stays unmapped). ADR-0020 makes one id one shape, so the reshaped datum is a **new** id,
`lesson_concept_coverage`, rather than an edited `lesson_concepts` — the same move ADR-0046 made
for `assessment_offerings` beside `lesson_assessment_items`. `lesson_concepts` stays exactly
what it was, for the packages already measured against it. **The LearnpackV2 adapter is v4**;
the one criterion that read the old id, `cr-cognitive-demand-rises-across-the-course`, now reads
the new one, in a **draft** `course-drafts-qa-v8` that changes nothing else. `workbench.yaml`
named it while it was the current version, so a fresh database published v8, accepted adapter
v4 and ratified `drafts-hybrid` against v8 in one pass. On a store that had already ratified
`drafts-hybrid` against v7, ratifying it against v8 needed the confirmation the criterion's
changed `requires` demands:
`ratify-assessor ... --confirm cr-cognitive-demand-rises-across-the-course`. The manifest now
names v9 (above).

**The three criteria that read every lesson were built, measured, and thrown away — and what
replaces them is a dump, not a criterion.** A branch took
`cr-later-lessons-apply-earlier-concepts`, `cr-concepts-introduced-before-use` and
`cr-adjacent-pair-has-a-bridge` at 19 calls per course, and the field runs read **8 of 8 and 9
of 9 lessons passing** where a hand reading of the same drafts said 7 of 8 and 8 of 9, **zero
violations ever** for the premature-use one, and **1 bridged pair of 10** for the third,
against an opening that plainly states its relation. Two criteria that cannot fail and one
that cannot pass: the machinery ran clean and discriminated nothing. The branch is not merged
and its commits are the record.

**The traces put the cause in what was asked, which is why no refactor was the answer.**
Three defects, none of them about cost or about the representation — the closed numbered
concept set read off `lesson_concept_coverage` was right, and 19 calls is cheap. First, **a
backward reference is measured by nobody**: the reuse criterion excludes it in as many words
("judged elsewhere") and sends it to the bridge criterion, which sees only adjacent pairs and
only the ends of each, so a reference to a lesson three back has no owner. Second, **the reuse
criterion asked for a comparison the model could not make** — work "the lesson which teaches
it did not already do" — while the corpus was `ordered[1:-1]`, so for every concept taught in
the opening lesson the other term of the comparison was not on screen; asked something
unanswerable, the model answered yes. Third, **one prompt written for one criterion was read
by two**: its whole framing looked backward and it capped touches at three "clearest", while
the premature-use criterion needs a FORWARD use, which is rare and was never asked for — its
zero violations are structural blindness, not a finding about the drafts.

**So `dump-concept-touches` is the step before the criteria, and it decides nothing.** One
call over a profiled draft, one row per place a lesson deals with a concept another lesson
declares, out as a markdown table with an empty column for the reader's own call. It is wider
than any criterion by design: every lesson is shown and marked (defect 2), concepts declared
**later** count as much as earlier ones and the direction is computed from the plan (defect
3), and every row carries the **zone** of its quote against the same 1200-character window an
adjacent-pair task reads (defect 1). The semantic call is split into **two independent axes** —
`mode` (`uses_as_known` / `re_explains` / `points_at`) and `newness` (`new_context` /
`same_as_taught` / `n_a`) — because the single `applied` fused them, and a fused answer cannot
be re-cut without paying for another run. What the plan and the text settle is never asked:
direction, distance and zone are computed here. Nothing is voted on, nothing is counted, and
no pass condition is consulted. It is **deliberately not identity (ADR-0034)**: no executor
imports it, `SOURCE_CONFIG` does not name it, its prompts stay out of the fingerprinted
templates, and tests pin that line in both directions — so it costs nobody a ratification.

**The extraction only became usable on the second model tried, and the first three drafts say
so.** Under the flash model the failures were all at the OUTPUT CONTRACT rather than at the
reading — `lessonId` dropped and entries answered by position, `mode` renamed to `type`,
quotes spliced with an ellipsis — and three drafts yielded 3, 1 and 0 touches with two runs
dead. Under `openai/gpt-5.6-luna` at `high` reasoning effort the same three yield 40, 97 and
77, one call each, no retry and not one row dropped for a quote that would not ground. Two of
the fixes on the way were ours and are worth keeping whatever model runs it: the quote is
asked for BEFORE the two classifications, because a field written after them is the field a
model drops, and a touch reported without one costs its row rather than the run.

**But the dump is a sampler, not yet an instrument, and no count out of it should be read as a
measurement.** One draft run twice at identical settings gave **40 touches and 29**, agreement
on `mode` for **half** the touches the two runs shared, and the same cited passage for under a
third. Part of that is benign — a lesson can deal with a concept in two places and both
citations are true, which also means a `mode` compared across two different sentences is not a
disagreement about the same thing — but the size of it is not. The reading rule that follows is
the union of repeats as the rows worth judging, with how often a row recurs treated as part of
what is being judged. **`medium` effort is not the saving it looks like:** it holds the
contract, runs four to five times faster for a quarter of the output tokens, and nearly stops
using `same_as_taught` (49 answers to 14 across three drafts, 31 touches moving one way against
4 the other, and zero on one draft) — which is the axis a bar gets set on.

**What is open is the reading.** The bar itself — what `applied` means, who owns a backward
reference, whether the premature-use question needs its own extraction — is written with the
owner after the tables are read, not before. Until that happens the three criteria stay
abstained and `inter-lesson-coherence` stays open, which is where they were.

**Noted while measuring, not built: the generator emits its own prerequisite graph.**
`files/concept_graph.json` carries concept → `prerequisites` → `maps_to_objective_id` and is
present in every generated draft on hand and in the repo's own fixture; its concept names
match `lesson_plan.json`'s `concepts_covered` exactly. That makes "does the delivery order
respect the prerequisites the generator itself declared?" a **zero-call** check of the plan
against itself. It is not built here: it wants a `DataRequirement` of its own, an adapter
version and an instrument bump, and it answers a different question from the three above —
plan against plan, rather than plan against the lesson bodies.

The repo can be run **without accounts or cloud** (local mode, ADR-0008): see the quickstart in
the root `README.md`.

### Slice 1 — MVP

| Block (`docs/design/08-code.md` §12) | Status |
|---|---|
| 1. Scaffolding + migrations + seed | ✔ |
| 2. identity + content_registry | ✔ |
| 3. rubric_authoring + evaluation + orchestration | ✔ |
| 4. golden_dataset + reporting | ✔ |
| 5. frontend (evaluator + admin console) | ✔ |
| Deploy (§10: Render + Netlify) | ✗ pending |

### Slice 2 — first increment complete

- **Design:** series `docs/design/09…12` + ADRs 0009–0015 (promoted earlier).
- **Code plan:** **`docs/design/13-code-qa.md`** (promoted) + **ADR-0016** (uniform automated
  assessors). GLOSSARY updated (Source axis `human | automated`;
  `Sufficiency` ex assembly); ARCHITECTURE and CLAUDE.md re-pointed.
- **Decisions taken during implementation:** **ADR-0017** (the declared surface of the
  evaluand is the package — supersedes ADR-0001; realized in block 5), **ADR-0018**
  (declared assessor coverage + `not_assessed` state — refines ADR-0016 §3; block 6
  realizes it), **ADR-0019** (coverage by criteria lineage + ratification per instrument
  version — refines ADR-0016 §3 and ADR-0018; block 6 realizes it), **ADR-0020**
  (`value_domain` mandatory and verified in `ContentProfile.ok()` — completes ADR-0014;
  realized before block 6, which is its first consumer), **ADR-0021** (the `fail`
  derived from absence: no quote, with its `derived` origin recorded — refines ADR-0018 §5;
  realized in block 6) and **ADR-0022** (mechanical intake of the `GenerationBrief` at
  content registration, hash identity dedup — **realized in block 7**) and **ADR-0024**
  (the generator link is declared, never defaulted; a discovered one is attributable later,
  once — realized right after block 7), **ADR-0023** (the fitness projection: optimization
  signal per quality, with the denominator that diverges from ADR-0018 §4 — realized after
  block 7), **ADR-0025** (pedagogical frames: the vocabulary is a swappable, disjoint
  namespace — **decided, deliberately not built**) and **ADR-0026** (a claim asserts about
  exactly one quality — realized with ADR-0023, which made the cost visible) and
  **ADR-0027** (package intake by mechanical discovery behind a port; content identity by
  content hash — realized after the increment, see the intake bullet under Open) and
  **ADR-0028** (a consumable URL declares a deployment, not a way to reach the bytes: the
  field becomes optional and a filesystem root never yields one — amends ADR-0027 §5 in
  part, does not supersede it) and **ADR-0029** (automatic profiling assumes http(s)
  transport; one policy subscription list for every process) and **ADR-0030** (the generator
  declares reference data about itself, not artifacts — `GeneratorArtifact` retired, see the
  bullet under Open) and **ADR-0031** (a generator is an entity; its versions belong to it —
  the lineage becomes a row, the name is typed once per generator, and the one act that still
  types one is guarded against a near miss). GLOSSARY
  reflects
  the five states, the automated assessor by lineage, `DataRequirement` with its two
  halves, the quote demanded only of executed scored, and `unknown` as a declaration.

| Block (`13-code-qa.md` §9) | Status |
|---|---|
| 1. CI (workflow + mypy scoped to new modules) | ✔ |
| 2. Renames + retirement of averages (ADR-0011) | ✔ |
| 3. Evaluand Registry widened | ✔ |
| 4. Evaluation Design (instrument + first real YAML) | ✔ |
| 5. Content Profiling (LearnpackV1 adapter + viewer) | ✔ |
| 6. Automated Evaluation (first assessor) | ✔ |
| 7. Evaluation Studies thin (+ brief intake, ADR-0022) | ✔ |

**After block 7 — the fitness projection (ADR-0023).** A read-side signal for optimization,
never a judgment: `GET /admin/studies/{id}/fitness` and `show-fitness` (CLI) compute, on read,
`pass / (pass + fail + no_evidence)` **per `Quality`**, rolled up to each
`PedagogicalDimension` as the unweighted mean of its **defined** qualities, at three grains —
per content, per generator version (counts pooled across its contents, unknown generators
excluded and named) and per study. `not_assessed` and `not_applicable` stay **outside** the
denominator, which diverges from ADR-0018 §4 on purpose and is stated in the ADR. An empty
denominator answers **`undefined`, never `0`**. Coverage, the formula version and the ratified
assessors travel with every value: dropping `not_assessed` means two assessor sets compute over
different populations, so the GA may only compare within equal coverage. It stays **out of
`study_reports.report`** (ADR-0011 untouched); the console shows it in a separate panel beside
the report, labelled as an optimization signal. Two enabling changes came with it: the
published `InstrumentVersion` now **freezes its `quality → dimension` map**
(`instrument_versions.quality_dimensions`, migration 0013 with backfill) because
`qualities.dimension_id` is global and mutable and would rewrite published studies
retroactively; and `evaluation.public` publishes `get_criterion_outcomes` — the un-aggregated
five states per criterion, which `judgment_claims.evidence_basis` cannot supply (it is counted
per claim, and claims excluded from the denominator have no row at all).

**The brief axis (ADR-0039), the first piece built for the collaborator's use.** The GA
experiment generates **several courses from one brief with one generator version** to measure how
much that version varies on a commission, and the projection could not express the grouping: the
three grains never named the brief, though `ContentInfo.brief_id` already reached
`compute_fitness` and the study report has labelled its contents since block 7. Now each content
section carries its `briefId` (`null` where the intake derived none) and the header carries a
**brief table** — one entry per commission, never per course, with `briefHash` and the brief's
text — covering the study's recipe **union** what its contents reference, so a commission that
produced no course reads as an empty group instead of vanishing. The hash is published because
the id is not portable: a UUID is minted per store and does not survive the local database being
rebuilt between generations, while `sha256(description + materialsHash)` (ADR-0022 §3) is the same
commission anywhere. It travels through `BriefDTO` → `BriefInfo`, which had never carried it.
**Nothing is pooled per brief**, and the ADR records why: across generator versions a pool mixes
individuals, and per brief × version it collapses exactly the dispersion the repeats exist to
measure — a consumer can derive the pooled value from labelled contents and can never recover the
dispersion from a pooled one. `FITNESS_FORMULA_VERSION` therefore stays `"1"`: no state entered or
left a denominator, so every value computed before this stays comparable with every value computed
after. The console's fitness panel gained a **By brief** block — one row per course, one column
per dimension, the commissions of the recipe with no course included — which is the only reading
that makes a version's variability visible to a person.

**Evaluating a study in batch (ADR-0040), the second piece built for the collaborator.** A
generation is a study's worth of courses — ~16 LLM calls each today, ~40 once the criteria that
read every lesson exist — and nothing ran any of it concurrently, so a generation was hours.
`evaluate-study` (CLI) is now one **run** in the shape `preview_runs.py` established, with three
differences that matter for real work: it persists (each course is a plain `EvaluateContent`, its
own session, its own transaction — batch is a loop over the existing use case), it uses several
workers, and it can be stopped. **The ceiling on requests in flight is not its business at all**:
`LLM_MAX_CONCURRENCY` (default 4) is enforced by a semaphore in the shared transport client,
which is the only place that sees every call however many levels of fan-out sit above it — so the
lesson-level fan-out, when it arrives, nests inside this loop without reopening the question. The
slot is released before any backoff, the reactive half (429 + `Retry-After`) is untouched, and
concurrency is **access, not identity** (ADR-0034), so no assessor was bumped. **The unit is the
course:** ADR-0037 decides what happens inside one evaluation, this decides what happens between
them — a failure is one row of the summary and the batch carries on, except for a `configuration`
failure or a coverage bug (properties of the wiring, so the first one ends it) and three
consecutive transport deaths (the endpoint is gone; any course that completes clears the streak).
Everything refusable is refused before a call is paid for: study not open, no instrument pinned,
empty dataset, assessor unregistered or unratified. **Re-running resumes** — what this assessor
already evaluated is skipped — and **Ctrl-C stops starting**: what finished stays, what was in
flight writes nothing, and the summary still prints. Progress goes to stderr and one JSON
document to stdout, per course with its `briefId` (ADR-0039), which is what a GA script reads to
know a generation is done. Cancellation is a `ContextVar` token the transport checks before each
request — a call not issued is money not spent — and `Cancelled` derives from `BaseException`, so
no `except Exception` can turn a stop into a persisted evaluation of `execution_error`s. One
present defect was fixed on the way, and it is what makes any of this safe: `drafts-hybrid`
memoized its tasks in **module-level dicts** cleared at each dry run, so two overlapping
calibrations emptied each other's answers and, over one profile, one could be served the other's
— two repeats silently collapsing into one measurement. The caches are now scoped to one
evaluation; within a run nothing changed, so **no version was bumped**.

**The batch from the console.** The loop's only step that still needed a terminal was the one
in the middle: `/admin/studies` already declared, pinned, composed, opened and published, and
evaluating was CLI-only. Now `/admin/studies/<id>` carries an *Evaluation* card over the same
use case — `POST /admin/studies/{id}/evaluations` starts a run and returns its id (202), `GET
…/{run_id}` reads it while it advances, `POST …/{run_id}/cancel` stops it — composed in
`app/platform/batch_router.py`, beside `ratification_router.py` and for the same reason: the
act spans two modules. Three things are worth naming. The **durable count** ("12 of 20 courses
judged") is a query over the judgments, not the run's memory, so it survives a restart and
counts a batch someone ran from a terminal — which is exactly what an in-memory run cannot do.
The start dialog **only offers assessors that ratified the pinned version**, so the option that
would be refused is never shown (the ADR-0036 stance, applied here). And a second run over the
same courses is refused **409** while the first is alive: judgments are append-only and every
reader takes the most recent, so two batches over one course would decide by arrival order —
the one genuinely confusing outcome available, and the cheapest to prevent. Runs are kept in
memory, last ten, and the registry never forgets one that is still working. **No ADR:**
ADR-0040 decided all of it and named this surface in its `[future]`.

**The console area that worked and could not be used, in three PRs.** With the loop finally
end-to-end on screen, the owner used it and found the studies area *"extremely confusing"* —
which turned out to be three separate faults with one shape: the page told the truth about
nothing that had just happened.

**PR 1 — the page notices its own batch.** `queryKeys.studyReport` and `studyFitness` were
never invalidated anywhere in the repo and `/evaluations` was never polled despite a docstring
claiming it was, so after evaluating twenty courses the header still read "0 of 20 judged" and
fitness still read `undefined` until a hard reload. **That, not the wording, is why running the
batch a second time looked like the way to make something happen** — and why every course then
came back `skipped`. The run watcher now refreshes the study's whole story the moment a run
leaves `running`, once per run, waiting for the real ending rather than reacting to the cancel
act (cancelling answers while courses are still landing). The rest of the PR is navigation and
honesty: opening and publishing moved onto the study's own page, setup became three numbered
steps, the evaluate button says which of the three things it would do, `skipped` reads "already
judged", and the list became a list, newest first. One live defect fell out of it — cancelling
wrote the run into the cache and then invalidated a key that is that key's prefix, throwing the
answer away and refetching it. **The count remains assessor-blind** (`read_study_evaluations`
counts judgments per instrument version while the batch skips per assessor); the UI says so in
a sentence and promises "up to N" rather than N, which is a stated limit, not a fix.

**PR 2 — two composed-on-read resources (ADR-0041).** `GET
/admin/studies/{id}/report/preview` runs the same `compose_report` over today's inputs, at any
status, minus `publishedAt` — removed and not nulled. `GET .../criterion-outcomes` carries one
section per criterion the instrument declares, so every one has a denominator, plus each cell's
own evidence; a published study is read through the judgments its report froze, named in the
payload as `judgmentBasis`. The five columns the cross-module query had been dropping (`quote`,
`locator`, `failure_mode`, `comment`, `execution_cause`) are now selected, which is what makes
**the quote behind a pass readable at all** — it was persisted for every pass, CHECK-enforced,
and reachable by nobody. `PublishStudy._compose` was extracted to `application/gathering.py` so
the publish path and the preview compose from one gathering; the refactor's gate was that the
three studies test files pass untouched, and they did. `show-preview` joins the CLI as its own
command. `compose_report` is byte-identical and `SCHEMA_VERSION` did not move.

**PR 3 — a report a person can read.** The old view was one always-open card per course (twenty
courses, twenty expanded panels), ids as row labels, quotes inlined at whatever length they
came, and eight caveat rows mostly saying "none". It now opens on what can be acted on: the
weakest claims with their distributions and coverage, the most-failed criteria — the question
that turns a round into an edit of the generator, unanswerable before for want of a denominator
— then the courses one collapsed row each, then all eight caveats behind one line. Expanding a
criterion shows its pass condition, its declared failure modes and every course that failed it
with the passage the judge read, and offers both readings: the generator's fault, or the
check's, the second being a deep link into `/admin/calibration` with the course and instrument
preselected and that criterion's row marked. **The report is now rendered at every status**, the
preview standing in until the document is frozen, with a band at the top saying which one is on
screen — and `publishedAt` is *unreadable* through the shared type, so the old unguarded
"Published \<date\>" cannot be written again. Readiness and the evaluation card no longer render
on a published study: readiness is computed from today's ratifications and adapters, so on a
frozen report it can contradict the document beside it. Human text (statements, pass conditions,
failure modes) is joined from the immutable instrument version rather than denormalized into the
frozen row.

**A judgment now names its author (ADR-0042, first of two PRs).** The report froze *which*
judgments it reflected and never *whose*: `latest_judgments` keyed on the content alone, so
half a study judged by `drafts-hybrid:10` and three courses repaired with `:11` published as
one document that could not say so — and the fitness value the GA reads averaged across both
while publishing `ratifiedAssessors`, who was *permitted* to judge. The fix needed **no
migration**: `quality_judgments.evaluation_id` is a unique FK and `evaluations.assessor_id` is
NOT NULL, so the author is a total function of what is already persisted. Evaluation joins
only `evaluations` — its own table — and the **label** comes from Identity's batched
`list_assessors`, because `source_config->>'name'` is ADR-0016's identity rule and re-encoding
it in a second module is how two copies drift; the gateway crosses to both, which is what a
gateway is for. Reading `assessors` from Evaluation's SQL would have been the repo's first
cross-module table read and would have passed the architecture test, which checks imports and
not SQL. The report now carries the assessor per course and an `assessorsUsed` header, plus a
ninth caveat (`mixedAssessors`) that fires above one author; the fitness publishes
`assessorsUsed` beside `ratifiedAssessors` with a note saying which is which; the criterion
matrix names them beside `judgmentBasis`; and the durable count is split per assessor, so the
console's *"Up to N"* — an honest patch for a number that could not be computed — becomes an
exact one in the dialog, where the assessor is known. **`SCHEMA_VERSION` moves to 2**, which is
ADR-0041 §8's own test applied in the other direction (there the output was byte-identical;
here it changed) — and since nothing branches on it, the real protection is that every new
frontend field is optional and read defensively: a report frozen at version 1 is the record it
is. The caveats line stopped spelling its own count in prose, which had been wrong once
already.

**And now a study pins its judge (ADR-0042, second of two PRs).** A study fixed two thirds of
what defines its result — the dataset and the norm — and left the third to whoever ran the
batch. `studies.assessor_id` (migration 0019) is the third: pinned once, before opening,
refused unless that assessor has ratified the pinned version, and `open()` refuses without
it. `prepared` now derives from **both** pins plus a composed dataset, so a study cannot read
"ready" and then decline to open. Every study read — report, preview, fitness, matrix, the
durable count — filters judgments by the pin, **in SQL**: a judgment by anyone else is not
this study's result, and transferring its quotes in order to drop them would be paying for
the wrong answer. One clause with a null-means-everyone parameter, not a second statement
built by branching, because the same reads still serve studies that predate the pin.

**The backfill is the part that had to be right the first time.** It fills the pin only where
the author is unambiguous, and it reads a **published** study through the judgments its frozen
report recorded rather than through today's most recent (ADR-0041 §6): pinning whoever
re-evaluated a course after publication would make every read of that study filter out the
very judgments its document is composed from — a matrix reading `0 of 20` with `basis:
publishedReport`, indistinguishable from a report that legitimately reflects none. Its three
shapes are pinned by a test that imports the statement from the migration.

**The batch stops asking.** `evaluate-study --assessor` and the HTTP field become optional and
are **refused on a disagreement** rather than obeyed or ignored — both of those are silent,
and this is the one thing a run about to spend money must not resolve on its own. The
single-content `evaluate` stays study-agnostic by design: it does not know which studies a
content belongs to, and under the filter a stray judgment simply does not count, which is the
property the pin buys. In the console, setup becomes four steps (the assessor is pinned
**second**, since the list it offers is filtered by ratification against the pinned version)
and the evaluate dialog loses its picker — the last place where "whose result is this?" was
answered by whoever clicked.

**A stale schema now refuses at the door, and the incident that asked for it.** The first real
batch died mid-course on `UndefinedColumn: execution_cause`: the development database was at
revision 0017 while the code expected 0018 (ADR-0037's migration). The suite could not have
caught it — `conftest` migrates the test database at session start, so green tests say nothing
about the store anyone actually runs against. `app/platform/schema_version.py` now compares
`alembic_version` against the checkout's head at **both doors** (`main.py` and the CLI's
`main()`): under `AUTH_MODE=local` a mismatch **refuses to start**, which is ADR-0008's own
idiom for a dev box; anywhere else it warns, because a deploy may start a process while the
migration step is still running, and refusing there would break the thing the check exists to
protect. A database it cannot reach says nothing — that is a different failure with its own
reporting, and answering "your schema is stale" to a connection refused would be a lie where
someone is looking for the truth. Three states, three remedies: never migrated · behind
(`alembic upgrade head`) · **ahead of this checkout**, where migrating would not help and the
stale thing is the code. One pre-existing defect fell out of writing its tests: alembic's
`fileConfig` runs with `disable_existing_loggers` on by default, so migrating in-process was
switching OFF every application logger created before it — the whole suite's warnings, unheard
since block 1. `alembic/env.py` now passes `False`.

**After block 7 — generator attribution (ADR-0024):** registering a content now **demands a
declaration** — a generator version or an explicit `unknown` — at every entry point (form,
API, canonical bulk import, `register-package`), so the accidental null that
cost a content its place in generator-level accumulation cannot happen silently. And what is
declared unknown is **repairable**: `attribute-generator` (CLI) and
`POST /admin/contents/{id}/generator` record a generator learnt later, **once and one-way**
(`unknown → known`, never `known → other known`), with who and when (migration 0012). A
content attributed after its study opened counts when the report is composed at publish;
reports already published keep their frozen caveat.

**Block 7 delivered:** the `evaluation_studies` module (migration 0011: `studies`,
`study_recipe`, `study_dataset`, `study_reports`) with the lifecycle
declared → prepared → open → signed_off, the report composed on-read when the study is
signed off (ADR-0006 style; caveats always, never a cross-claim aggregate), the composed queries **matching**
(`GET /admin/instruments/{version}/matching?package_format=…`) and **readiness**
(`GET /admin/studies/{id}/readiness` — gaps per claim plus the ADR-0019 study-level gap
"no ratified assessor"; informs, never blocks), the CLI loop
(`declare-study | update-study | open-study | sign-off-study | show-report`),
and the `/admin/studies` console. The brief intake (ADR-0022) landed in the same PR:
registration derives the brief from `.learn/initialSyllabus.json`, hash identity pairs
registrations automatically, and the intake dispatches through a **per-format adapter
registry** (`BRIEF_INTAKES_BY_FORMAT`, the profiling pattern) — LearnpackV2's native
briefs will be one new entry, no registry or wiring change. `import-learnpack` gained
`--base-dir` (its canonical path also carried a latent ADR-0017 `TypeError`, now fixed:
the canonical JSON takes `artifacts`/`brief_id`/`generator_version_id`/`edit_provenance`,
no `metadata`).

**The drafts lineage's first assessor (`drafts-structural` v1).** The `course-drafts-qa`
lineage can now ratify: an assessor artifact declares itself against it — 7 executed
criteria and 22 named abstentions over the 29 of v2, a superset of v1's 22, so both
published versions ratify with the one artifact. It is a copy of `structural` v1, not an
import (ADR-0016: shared code would tie the two identities together), restricted to the
criteria this lineage defines, with one deliberate difference: the objectives count metric
is `declared_objectives_count`, because the lineage mints a data requirement named
`declared_objectives` (the objectives themselves) and a report must not carry one name with
two meanings. `structural` v1 is untouched and keeps its metric name in its own lineage,
where nothing collides. With the registry past one package, `evaluate` now requires
`--assessor <name>:<version>` explicitly — the single-package default is gone.

**The first LLM-carrying assessor (`drafts-hybrid:2`, ADR-0034 — superseded by
`drafts-hybrid:3` below, and kept here because it is where the extract-then-decide half
was decided).** One hybrid artifact
for the `course-drafts-qa` lineage: the seven structural executors copied from
`drafts-structural` plus **five semantic criteria** where an LLM extracts or classifies
(outcome statements and their verbs from the opening lesson, Bloom levels per declared
objective, sophistication of the planned concepts) and **code decides** — counts, order
checks, a trajectory rule with its constants pinned by tests. It is one artifact and not a
separate LLM-only assessor because judgments do not combine across assessors (the report
and the fitness read the most recent judgment per content); within one study, evaluate
each content with one assessor. The boundary ADR-0034 draws: models, prompts, temperature
and decision constants are **identity** — sampling included: the output budget and
whether the model may reason are declared too, because they decide what comes back — pinned
in code and declared in `SOURCE_CONFIG`
(with a prompts fingerprint the ratification drift-guard checks), while the transport — a
shared httpx client in `app/platform/llm.py`, OpenRouter by default via `LLM_API_KEY` /
`LLM_BASE_URL` — is **environment** and re-versions nothing. Structured output with
feedback retry, verbatim grounding of every extracted quote, per-profile task memoization
(three calls cover five criteria), cost/latency reported as `llm_*` metrics; an
irrecoverable LLM failure **aborts the evaluation whole**, nothing persists.
`cr-objectives-verb-level-band` stays abstained on purpose: `difficulty` is nullable in
this format and neither pass nor fail is honest against a null anchor — the recorded exit
is a `declared_difficulty` data requirement (instrument + adapter change, not taken).
The instrument was bumped to **v3** with it: `cr-objectives-non-decreasing-demand` now
requires `learning_objectives` (the datum the executor actually reads in a format that
declares objectives structurally) instead of the bodies where an older format left them
implicit. Ids and claims are verbatim v2.

**The first judged criteria (`drafts-hybrid:4`).** Careful with the numbering here: the
*instrument* `course-drafts-qa` is at v3 and the assessor is at v4; they are unrelated
artifacts and their numbers do not track each other. Everything before this kept the model
on the supply side — it extracted or classified and code decided — because that half was
cheaper and because a decision rule in code is one anyone can read. v3 takes the first
**seven criteria whose verdict is the model's**, chosen not by how interesting they are but
by what they cost: these are the ones answerable **without reading every lesson**. Four
judge the two frame lessons (`cr-opening-lesson-connects-backwards`,
`cr-closing-lesson-integrates`, `cr-closing-lesson-projects-forward` and `cr-arc-character`,
which reads both because its condition asserts about the pair); two read the declared
objectives against the shipped assessment; one reads what that assessment draws on.
Coverage goes **12 → 19 of the 29**, at one call per criterion — about ten LLM calls per
evaluation, which is still cheap enough that a dry run can be read in a sitting. The nine
that remain all share one shape: they read **every** lesson body, one call per lesson, per
pair or per module, which is a different order of cost and a different decision.

Two of the seven are not judgments at all, and the artifact says which: *every objective
has an assessment item* is arithmetic over a mapping the model supplies, and *assessment
reaches back* is a count over lesson references constrained to the identifiers the plan
declares. They needed a model for the mapping, not for the verdict.

What keeps a judged criterion reviewable is three rules, all in `judgments.py`. **The
question is the instrument's own `pass_condition`**, passed in from the `CriterionSpec` the
executor already receives and never retyped into the assessor — so there is one source of
truth for what a criterion demands. **The answer carries a quote checked to be a verbatim
substring of the text shown**, fed back on violation and fatal when persistent, so what a
report displays is what the judge read (ADR-0009). And **a `fail` names which of the
criterion's declared failure modes it saw**, validated to be in range: the judge decides
inside a vocabulary it did not write, and an invented mode is a contract violation like any
other. The answer's field order is `reason` → `evidence` → `verdict`, because JSON mode
emits fields as the model writes them and a verdict-first shape would commit before
reasoning — which is how v3 gets the effect of thinking while `reasoning` stays at
`effort: "none"` and the budget that killed v1 stays spent on answers.

One consequence is new and worth stating: **the text of the instrument now enters the
question literally**, so bumping the *instrument* changes what the judge asks without moving
the assessor's `promptsFingerprint`. That is governed rather than accidental — ratifying an
assessor against a new instrument version is an explicit act (ADR-0019) — but it is the
first time the two artifacts couple this way.

`SAMPLES = 1`: one call per judgment, declared in `SOURCE_CONFIG` because how many answers
a verdict is decided by decides which verdict survives. Voting k=3 recovers real accuracy
(the variance outlives temperature 0 — it comes from how the server batches work, not from
sampling) and costs three times as much in money and latency; the bottleneck today is how
fast a human can read what the judge answered, and a judgment nobody has reviewed is not
improved by being made three times. Raising it is a version bump, not a tuning knob.

**What the first three calibration runs found, and why there is a v4.** The judged criteria
met the real model three times: two runs finished, one died. All three failures were the
same thing, and none of them was the model judging badly. Asked for **one** continuous
quote, the model answered findings that rest on **several** places in the text by stitching
passages together with `...` — and the grounding check rejected an answer whose verdict was
right. In the run that died, `assessment_verification_match` had correctly spotted that
three objectives declaring a performance ("apply CSS until it matches this screenshot",
"create a navigation bar with Flexbox") were measured only by multiple-choice and
fill-in-the-blank items — the criterion's failure mode 0, exactly. It was refused three
times for how it cited that, and the three answers were **byte-identical**: at temperature 0
the same conversation gives the same reply, and the feedback named the symptom ("not
verbatim") rather than the rule, so the model had nothing to change. The other run survived
the same way by luck — `arc_character` stitched twice and produced a continuous span on its
third and last attempt. The six single-lesson judgements across the three runs never failed
once: the criteria whose corpus is a **set** (`arc_character` reads two lessons,
`assessment_verification_match` reads N objective blocks) are exactly the ones the contract
did not fit.

v4 is that contract corrected, three changes and all of them identity. **`evidence` is a
list**, one entry per place in the text, each still a continuous span — the quote shape now
matches the shape of a finding. **Grounding tolerates whitespace when matching and stores
the source's own span**: a model quoting across an indented line renders the indent as a
space, and three of the six rejected fragments failed for that alone, which is not a finding
about the course; what a report shows is still the course's text, never the model's
rendering, so ADR-0009 is untouched. **The feedback names the broken rule** ("do not join
passages with an ellipsis — split them into separate entries"), and the retry loop now stops
when an answer repeats verbatim instead of buying two more copies of a fixed reply. Replayed
against v4, the answer that killed the run gets the actionable message, and all six of its
fragments ground.

The first `ExecutorResult` quote is the first passage rather than a concatenation of them,
with the rest carried as a metric: each entry stands on its own as something a reader can
find in the course, and joining them would put text in a report that the course does not
contain contiguously.

**What five clean runs then measured: the judge is 80 % consistent, and the missing 20 % was
the instrument.** With the contract fixed, `drafts-hybrid:4` ran five times without a single
retry — three times over one draft (HTML) and twice over another (CSS), which is what makes
the numbers mean something: repeats of the **same** input are the only way to separate "the
judge varies" from "the courses differ". Pairwise agreement over identical input was **16 of
20**. Three of the five judged criteria were unanimous everywhere; the CSS draft was 5 of 5
stable; every disagreement landed on two criteria of the HTML draft.

Reading the traces, neither wobble was the model being unreliable. In
`cr-opening-lesson-connects-backwards` the three runs quoted **the same two passages** and
read them opposite ways — one run even naming the evidence and ruling against it ("despite
mentioning everyday web pages and a blueprint analogy…"). The condition admits "everyday
experience" and the draft appeals to it; what it never said is whether an **analogy** counts
as relating the new material to the familiar. And `cr-closing-lesson-integrates` was worse
than ambiguous: it and `cr-closing-lesson-projects-forward` evidence the **same claim** under
`conjunctive` sufficiency, so both must pass — while the same sentence ("CSS adds the paint,
JavaScript adds the lights") is rewarded by one for naming what comes next and failed by the
other for "introducing new material". **That claim was unsatisfiable for that shape of
closing**, and no amount of evidence would have fixed it. The oscillation was the judge
finding both readings because both were written.

**`course-drafts-qa` v4 is those two sentences, and nothing else** (`bump-instrument` → edit →
`import-instrument`; ids, claims and `requires` verbatim v3). The opening criterion now says
an explaining analogy counts as relating; the closing criterion's fail clause now says
**teaches** new material instead of consolidating, and says outright that naming what comes
next is not teaching it — so the defect it was written to catch, a wrap-up that smuggles in
content, is still caught. **No assessor version was bumped**: the judge is handed the
`pass_condition` from the `CriterionSpec`, so the instrument decides the question and
`drafts-hybrid:4` is untouched. It sits as a **draft** — publication is a human act, and a dry
run accepts drafts, so calibrating against it needs nothing else.

**Measured against v4: the wording was most of it.** Six more runs, three per draft, all
against v4. The HTML draft — the one both wobbles came from — is now **5 of 5 criteria
unanimous across three repeats**, and both reworded criteria settled on the reading their new
text implies. Pairwise agreement over identical input went from **16/20 (80 %) to 28/30
(93 %)**, and the whole residue is a single (draft, criterion) pair.

**That residue is the useful part: `cr-closing-lesson-projects-forward` on the CSS draft is a
coin flip, and its text was never touched.** Its `pass_condition` is byte-identical in v3 and
v4 (checked against the prompts as sent, not the YAML), so its six observations are six
answers to one question about one closing: **three `pass`, three `fail`**. What makes it
diagnostic rather than merely noisy is *how* they split — all six quote the same single
passage and describe the same facts in nearly the same words ("summarises what was learned and
says the learner can now style any webpage… *practice and new properties*"), and then divide
on whether those facts clear the bar. One answer states both readings before choosing:
"projecting onto future practice and new properties, **but** does not explicitly situate it in
a learning or professional path beyond that." The model agrees on the facts every time and
disagrees only on the threshold — which is a criterion that does not say where its threshold
is, not a judge that cannot read. The open question is whether "more practice of the same
skill" counts as *what comes next*; either answer is defensible and the text picks neither.
It is not cosmetic: this criterion and `cr-closing-lesson-integrates` evidence the same claim
under conjunctive sufficiency, so for that draft the **claim itself** is a coin flip.

**All three of those are now built, and the fourteen runs' four findings live in the
runbook.** `course-drafts-qa` **v5** writes the missing threshold: projecting forward means
naming something beyond the course, and telling the learner to keep practising what was
already taught is not it. The permissive reading was available and was rejected on the
ground that nearly every closing says *something* about the future, so admitting "keep
practising" would leave the criterion passing almost everything. One `pass_condition`, ids
and claims verbatim v4, imported as a **draft**.

`drafts-hybrid` **v5** carries the other two. **Grounding no longer rejects a quote over
markdown**: lesson bodies are markdown, a model quoting a sentence that carries `**bold**`
drops the markers about as often as it keeps them, and byte comparison called that a
hallucination — the same false negative whitespace used to cause, with the same answer.
Emphasis is invisible to the match; the stored quote is still the source's own span, so
ADR-0009 is untouched. (The span runs from the first matched character to the last, so
markers inside it survive and a marker run on the boundary does not — still verbatim, which
is all a quote has to be.)

**And a judgement is now decided by a vote:** two samples, a third only when they split, the
majority wins. That is exactly the verdict an always-three majority would give — two
agreeing samples cannot be overturned — at ~2.2 calls instead of 3, which is why it is not
simply k=3. Every judged criterion reports its split as a
`judgment_agreement_<task>` metric of `{samples, agreed}`, and that number is the point as
much as the verdict is: a criterion that keeps coming back **2-1 is a bug report about the
instrument**, since that is the signature of a threshold nobody wrote down. Sampling stays
necessary after the wording fixes because borderline instances surface **one per draft** —
two drafts produced three different oscillating criteria, one each — so there is no
enumerable list of "hard criteria" to sample selectively. `SAMPLES`/`MAX_SAMPLES` are
declared in `SOURCE_CONFIG` for the same reason a model id is: how many answers decide a
verdict decides which verdict survives.

**And the evidence list gained a ceiling, found by a run that was not supposed to teach
anything.** A calibration fired against instrument v5 with a server still holding v4 in
memory — the instrument is data and reloads per request, the assessor registry is code and
loads at import — so it exercised the new criterion wording under the old judge. What it
exposed had nothing to do with either: `arc_character` looped a nine-quote cycle until the
token limit cut it off at **191 evidence entries, 18 of them distinct**, spending 8000 output
tokens, three quarters of that whole evaluation. The list v4 introduced to fix stitched
quotes had no bound, and with a vote such an answer is paid for two or three times.
`MAX_EVIDENCE = 12` is set against the observed spread — legitimate answers run 1 to 8
passages, the 8 belonging to the criterion that reads one block per declared objective — and
is checked before the quotes are, so a runaway list produces one readable complaint instead
of one per entry. Replayed against the cap, the real 191-entry answer is refused by it.

That misfire is worth keeping as a note about the machine, not just about this bug: an
instrument version takes effect the moment it is imported, an assessor version takes effect
when the process restarts, and the console shows which assessor is actually loaded.

**Degeneration turned out not to be a property of judging.** The judge's budget was cut
first, on the reasoning that only judging had ever looped; the next pair of runs falsified
it. One died in `assessment_reach`, whose `referencesLessonIds` filled with repeated and then
invented lesson ids until the 8000-token budget was gone — 124 seconds for nothing. What
invites a loop is a **free-length array in an output schema**, and the two extraction tasks
here have one each. Both are now bounded the same two ways: their own output budget (2500,
about five times the measured maxima of 424 and 518, so a draft several times larger still
fits) and a **no-duplicates rule in every free-length array** — evidence quotes, matched item
indices, referenced lesson ids. Repetition is exactly the shape a degenerating answer takes,
and refusing it also bounds each list by what the draft contains: a mapping cannot name more
items than exist, a reach more lessons than the plan has. `tasks.py`'s three extraction tasks
keep the shared budget on purpose — none has degenerated, and `concept_trajectory` has
legitimately spent 2412 tokens on a long plan.

**A provider signal worth recording, not yet acted on.** Every `finish_reason: length` seen
across this campaign — six of them — was served by the same upstream, while fourteen others
produced none. It is suggestive rather than conclusive at that sample size, and it is the
pinning question ADR-0034 §3 leaves open, now with evidence attached. Deliberately not fixed
here.

**Before that, a run took ten minutes to die, on the half of the problem the cap could not
reach.** `MAX_EVIDENCE` bounds what a judgement may CONTAIN and is checked once the answer
has arrived, so it stops garbage being stored, not minutes being paid. A second sample of
`cr-closing-lesson-projects-forward` repeated one sentence into the evidence array until it
ran to the 8000-token budget — 32 000 characters — and since a truncated answer is a
violation, it was fed back and did it twice more. Three attempts, 24 000 output tokens, 558
seconds, no result. Two bounds close it. A judging call now gets **1500** output tokens
rather than the extraction tasks' 8000: judged answers that completed run a median of 153
tokens and a maximum of 773 across every run so far, so the budget is about twice the widest
real answer and cuts a loop off in seconds. And **an answer stopped at the limit is no longer
retried** — the same lesson v1 taught about `finish_reason: length`, which had never once
been recovered by asking again; the exception names the budget and the spend instead. Only
when the answer is unusable: one that hits the limit and still parses and validates is
returned, since a usable answer is a usable answer. That failed run would have cost one
attempt, ~1500 tokens and ~35 seconds.

**The run before it died on a defect of the same family.** A corpus that a task demands
verbatim quotes from was being built with `json.dumps`, so an assessment item reading
`class="title"` reached the model as `class=\"title\"`. The model quoted what it could read
— the course's actual text — and the grounding check refused a citation that was correct.
Then the answer came back byte-identical, because from where the model stood it HAD copied
exactly, and the repeat detector did its job and ended the evaluation. Two mechanisms in a
chain: a false rejection, and a correct stop on top of it. The two corpora that were
serialized are now plain labelled lines, which removes the class rather than adding a third
tolerance to `locate` after whitespace and emphasis — encoding a text and then demanding the
decoded form back is the defect, not a matching subtlety. It is content-dependent, which is
why it took this long to appear: of the two mapping corpora in the traces one carries two
escaped quotes and the other none, so one draft triggered it and the other never could.

**The four findings are now reference, not status.** They were general enough to outlive the
campaign that produced them, so they sit in `backend/README.md` under *What repeated runs
tell you*, beside the section on reading a single trace: where the model disagrees tells you
whose defect it is (same facts and a different verdict is the instrument's; different facts
are the judge's) · writing the missing threshold beats voting, because ambiguity is not
variance · borderline instances belong to (content, criterion) pairs, so selective sampling
has nothing to select on · and none of it is diagnosable unless the judge quotes its
evidence. With the caveat that belongs next to them: **self-agreement is not correctness**,
and a criterion can be perfectly stable and stably wrong.

**Not yet measured:** whether v5's threshold settles the criterion it was written for. Three
runs of the CSS draft answer that, and one of the HTML draft confirms nothing that was
already unanimous moved.

**Failure isolation is decided (ADR-0037) and its first of three PRs is this one.** The
four calibration deaths above — each one task degenerating inside an otherwise healthy
evaluation — falsified ADR-0034 §4's bet that whole-run aborts stay cheap, so its §4 is
superseded: an execution failure becomes a **sixth outcome state, `execution_error`**,
minted by the derivation from a typed failure (the assessor raises, the machinery derives —
ADR-0018 refined, not broken), carrying a structured cause `{task, kind, message}`, with a
**failure budget** that keeps the whole-run abort as the limit case and a **three-way retry**
(contract → feedback as today · degeneration → one clean-conversation retry · transport,
configuration and `finish_reason: length` → never). The work lands in three PRs so main
stays green at each step: **PR 1 (merged)** taught the state to every consumer before
anything produces it — domain vocabulary and validator, migration 0018 (CHECK + the
`execution_cause` jsonb column), repository roundtrip, `evidence_basis`/judgment coverage,
the report's `insufficiencyCause` (never `"unknown"` for a run failure) and its
always-present `executionErrors` caveat, the fitness partition (state excluded from the
denominator; unknown states now raise instead of vanishing; `executionErrors` published in
`assessorCoverage`, extending ADR-0023 §7's equal-coverage rule to execution variance),
the preview API contract, the CLI printer, the console (badge, cause in the evidence cell,
fitness-preview column, study caveat row) and the GLOSSARY. **PR 2 (this one)** is
`drafts-hybrid` **v6**, the retry corrected inside the assessor package: every failure now
carries a machine-readable kind (`transport · configuration · response · budget · contract
· degeneration · profile` — the platform taxonomy preserved instead of collapsed into one
message string), a degeneration buys **one retry on a clean conversation** (nothing of the
broken round fed back; a second identical degeneration raises as the poison case; budget,
transport and configuration are never clean-retried), failures are **memoized like
answers** so the criteria sharing a task degrade together with one cause and without
re-asking a degenerated question, and every task reports `clean_retries` inside its
`llm_*` metric — verdicts that needed a fresh conversation are a shifted population. The
retry conversation shapes which answer arrives, so this is identity: v6 inherits no
calibration. **PR 3 (this one) closes the decision**: the derivation catches the typed
failure at the executor boundary and mints `execution_error` with its cause — case (e) of
the precedence, still mechanical, since raising is not deciding — bounded by
`EXECUTION_FAILURE_BUDGET = 0.25` of the criteria mapped for execution (`drafts-hybrid`'s
19 tolerate 4; an instrument with ≤3 executable criteria tolerates zero, which IS
ADR-0034 §4 as the limit case). Below the budget the evaluation persists with the
successes' metrics; past it the original failure propagates and the run aborts whole,
nothing persisted. A registration bug (`InvalidAutomatedEvaluation`) is never softened
into an `execution_error`. The CLI and the preview page report the same reality: a dry
run with a failed criterion ends `done` with the cause on the row and a red step;
exceeding the budget is the `assessor_failed` ending it always was.

**With the three PRs merged, calibration is UNPAUSED.** The next act is the one the
campaign was interrupted for: run the v5-threshold measurement (three runs of the CSS
draft, one of the HTML draft) under `drafts-hybrid:7` (below) — remembering a bump
inherits no calibration, which is its point.

**The first field exercise of ADR-0037, and why there is a v7.** Two calibration runs the
day the three PRs merged: the CSS draft finished clean (31 calls, zero retries of any
kind); the HTML draft finished **with one `execution_error` absorbed by the budget** —
the machinery's first real save, where before ADR-0037 the whole run would have died at
call 15 of 16. The failed call is instructive: AtlasCloud answered a 200 whose
`message.content` is **null** while `message.reasoning` carries 9,652 characters of the
model working the actual problem — in Chinese — with usage 0/0; the platform client
correctly refused it (kind `response`, never retried) and the criterion degraded with its
cause readable on the page. The same run's `objectives_classification` was served by
Phala: a clean 60-token answer billed as **3,491 output tokens** after 36 seconds of
invisible reasoning. Both anomalies are one phenomenon — **upstreams that ignore
`reasoning: {effort: "none"}`** — and OpenRouter's own documentation shows why: `effort`
is documented for OpenAI/Grok models, not this family, so for some upstreams it was never
an instruction at all. **v7 says it both ways**: `{effort: "none", enabled: false}` —
`enabled` being the boolean OpenRouter can translate more broadly. Belt and braces, not a
guarantee: an upstream that ignores the whole `reasoning` object still ignores it, which
is the open provider-pinning question (two more data points on its pile, providers named
in the traces), not this bump's business.

**What nine runs under v7 then measured (3 CSS + 3 HTML of the calibration pair, then
three new courses).** The threshold verdict first: **v5's wording settled the criterion it
was written for** — `cr-closing-lesson-projects-forward` on the CSS draft came back 2-0
*fail* in all three runs, six samples without one dissent. The borderline moved to the
HTML draft: its majority verdict (*pass*) was stable across all three runs — the vote
doing its job — but the split came back 2-1 twice, which is the recorded signature of an
under-specified edge, now on the neighbour's closing. `assessment_verification_match`
wobbled 2-1 once on HTML. Every other judged criterion was unanimous in every run.
Three more findings, each with the provider named in the trace:

- **`enabled: false` is not enough either**: under v7, AtlasCloud billed 1,139 output
  tokens for a ~97-token visible answer — it ignores both reasoning fields. The cost
  leak's remaining fix is the provider-pinning question, whose pile keeps growing.
- **Every capped runaway of the campaign — three — came from Sail Research**, and all
  share one new shape: *enumeration* degeneration (item indices counting 0…806 with a
  null for good measure; the full lesson inventory recited), which evades the
  no-duplicates rule by producing distinct values and is refused by the range/id
  validators instead. The failure budget absorbed every one.
- **The feedback loop recovered six real misquotes across the new courses** at one extra
  call each — quote-start capitalization ("These" for "these" mid-sentence), a dropped
  word, a passage quoted twice — first field confirmation that actionable feedback pays,
  and that grounding is catching real alterations, not formatting.

**v8 — a budget cut buys the clean retry too.** The v1 lesson ("length is deterministic,
retrying never recovered one") was measured over feedback retries, where the broken answer
re-enters the same conversation; a conversation rebuilt from scratch re-rolls the serving.
`CLEAN_RETRY_KINDS = (degeneration, budget)` is declared in `SOURCE_CONFIG`; a usable
capped answer still returns without spending the retry, and transport/configuration stay
never-retried.

**Six runs under v8 (3 HTML + 3 GitHub): zero exceptions, and the retry earned two saves
in its first session.** A judge call cut at its 1,500 budget was answered cleanly by a
fresh conversation — served by the SAME provider seconds later — and a mapping that came
back byte-identical after feedback (the degeneration signature, over an answer missing two
of three objectives) completed on its clean conversation, again on the same provider. That
same-provider save **refuted the "deterministic per provider" theory the v8 rationale was
first written with** (the docstrings now say what the field showed): runaways are
stochastic per request, strongly provider-correlated — every capped cut of the campaign
remains one upstream's, which keeps feeding the open pinning question without changing the
mechanism. Feedback recovered three more incomplete-mapping answers at one extra call
each. **The instrument signal of the night:** `cr-closing-lesson-projects-forward` on the
HTML draft produced its first judgment-level flip — one of the three runs decided 2-1
*fail* where every other run (five, across v7 and v8) decided *pass* — and
`cr-opening-lesson-connects-backwards` on HTML went 2-1 twice after being unanimous all
campaign. The recurring 2-1s were the warning; the flip is the bug report: the HTML
closing sits ON the v5 threshold, and deciding it belongs to the instrument's next
wording, not to more sampling.

**`course-drafts-qa` v6 is that wording, and nothing else** (`bump-instrument` → edit →
`import-instrument`; ids, claims and `requires` verbatim v5; drafts-hybrid untouched — the
judge reads the `pass_condition` from the spec, which is the property built for this).
Fifteen samples of the HTML closing quoted the same two passages and divided only on
whether *naming* CSS/JavaScript counts as *projecting*; v6 writes the threshold: a named
technology projects forward **when the closing offers it to the learner** — connects what
they can now do or build with the thing it names — and does not when it appears only as
background about other tools. The stricter reading (demanding an explicit "go study X
next") was rejected: the criterion's purpose is orientation, not curriculum prescription,
and "named and offered" still refuses generic futurology and the keep-practising closing
v5 was written against. The second edit closes the opening criterion's residual 2-1 the
same way: addressing the learner's everyday experience **of the subject** ("every web page
you have ever visited") counts as referring to what they already know, stated outright.
Sits as a **draft**. **Verified over five runs (3 HTML + 1 CSS + 1 GitHub):** the opening
criterion is fixed — unanimous *pass* where it had split 2-1 twice — and the closing
collapsed **onto fail** (3-0, 2-0, one residual 2-1): the judges read "offered to the
learner" as unmet by a closing that describes CSS/JavaScript without making them the
learner's next step. That direction was the opposite of the prediction the wording shipped
with, and the team reviewed the closing against it and **agreed with the fail** — the
criterion is now decidable and decided; nothing unanimous moved on CSS or GitHub. One
finding rode along, of a new class: a cross-run verdict flip on
`cr-assessment-matches-the-declared-verification` traced to **mapping variance upstream**,
not to the judge — one run's mapping gave obj-1 items (so its declared verification was
judged, and failed), the other's gave it none (so the corpus narrowed in code to an
objective whose item matches, and passed). Two different questions, both answered
correctly: chained-task sensitivity, recorded as a candidate for tightening the mapping
prompt (assessor identity), not the instrument.

**v9 — the provider deny-list (ADR-0038).** The §3 question ADR-0034 left open, answered
with the measurement it asked for: behind one model id, `sail-research` served **every
capped runaway of the campaign (seven of seven)** — reasoning past both disable flags into
the judging budget, one four-draw streak beating the clean retry and costing an
`execution_error` — and `atlas-cloud` billed invisible reasoning at 11–100× the visible
answer, once returning a null-content 200. The pool of possible judges is therefore
**identity**: `DENIED_PROVIDERS = (sail-research, atlas-cloud)` is pinned beside the retry
constants, declared in `SOURCE_CONFIG` (the ratification guard refuses drift), and rides
each request as a provider preference through the same extra-wire-fields seam as the
reasoning flags — the platform client is untouched and transport still re-versions
nothing. Deny rather than allow, on ADR-0034 §3's own recorded reasoning: an allow-list
buys consistency at an availability price already judged worse than the variance. The bar
for an entry is repeated, trace-documented failure — Phala (one 3,491-token bill) is
watched, not listed. Editing the list in either direction is a version bump.

**v10 — the wrapped outcome verb, the first bump the human review of verdicts produced.**
Reading the eleven runs of the v6 era by criterion found `outcomes_extraction` taking the
auxiliary of a wrapper as the verb and marking observable content non-observable: *"you will
be able to read, write, and structure your own web pages"* → `be able to`, false; *"you'll
go from writing plain, unstyled HTML pages to confidently styling…"* → `go`, false — while
the SAME structure in another draft, *"you will be able to contribute to any GitHub
repository"*, answered `contribute`, true. Inconsistency rather than a rule, the same class
as the historic `learn` case, and it lands on `cr-outcomes-observable-verbs` as a false fail
on two of the three drafts. The prompt now says to look through an enabling phrase and
report the verb of the action, to take the first when several are named, and to report the
wrapper phrase itself when there is no action behind it — a state about a topic is not an
observable action, which is the answer the criterion IS written to catch. **Two remedies
were rejected and the docstring says why:** a validator deny-list of wrapper verbs would
force a false answer, because `be familiar with` / `learn about` / `understand` are exactly
the answers a truthful extraction must be able to give; and rewording the task's own framing
line ("what the learner will BE ABLE TO DO" — the likely source of the priming) would move
which statements are LISTED, which is `cr-outcomes-present`'s evidence, leaving the field
verification with two variables. `objectives_classification` carries the same field and the
same risk and was left alone: the same reading found it resolving correctly in all three
drafts. Prompts are identity (ADR-0034), so v9's calibration does not transfer.

**Verified over six runs — three drafts of the campaign (one each) and two new ones (Git,
command line ×2).** Both wrapped statements now answer the verb of the action and an honest
`is_observable`: the HTML opening answers `read` and the CSS one `style`, where v9 answered
`be able to` and `go` and called both non-observable. **The guard held**: the GitHub opening's
*"you will be comfortable with that entire workflow"* names no action behind its wrapper and
stayed non-observable, beside its own *"be able to contribute"* → `contribute`. The statement
SET did not move (one, one and two statements, exactly the v6-era extractions), which is what
keeps `cr-outcomes-present` out of this bump. The Git draft shows the rule generalizing rather
than matching a list: *"You'll move from saving files with no history to making intentional
commits"* — a wrapper the prompt never names — answers `make`. Ninety-one calls, every one
`finish_reason: stop`, zero retries, zero failures, no denied upstream drawn.

**And a new draft produced a new instrument signal.** The command-line draft's opening states
NO outcome at all — it motivates ("the terminal is a conversation with your computer", "take a
breath, let's begin") and never says what the learner will be able to do — so the extraction
answers `{"outcomes": []}` in both of its runs, correctly. `cr-outcomes-present` fails on its
own failure mode 0, and `cr-outcomes-observable-verbs` passes **vacuously**, there being no
outcome phrased badly: the division of labour those two criteria were written with, doing
exactly what it says. Their claim is conjunctive, so it fails on the first. It is the first
draft of the corpus whose opening promises the learner nothing, and the criterion caught it.

**v3 is published, and the real model answers.** `drafts-hybrid:2` has been calibrated
against it from `/admin/calibration`: four dry runs over two courses, twelve LLM calls,
every one answered on the first attempt (47–307 output tokens, 2.6–14 s), all three
semantic tasks reaching the end — including `concept_trajectory`, which under v1 never ran
at all because the run died before it. The suite pins the decision rules over a faked
transport, so this is the only exercise the real
`deepseek/deepseek-v4-flash-0731` gets; each dry run spends ~3 calls and needs
`LLM_API_KEY`.

**Pending input from the team (drafts lineage):** *reading* those answers. The runs prove
the mechanism works, not that the judgments are right — whether the extracted outcomes and
the Bloom/sophistication classifications read sane against the packages is the human call,
and it has not been made. A concrete first case: the model marked *"You'll learn how to
target exactly which elements to style…"* as `is_observable: false`, on the verb *learn* —
the instrument's own rule doing exactly what it says, and precisely the kind of call that
has to be reviewed before a study pins this version. Every prompt and raw answer is on the
page and in the trace file (see *Observability of the LLM half*), so the review can be done
against what actually happened rather than against a summary. The seven judged criteria
have now met the real model fourteen times, and what those runs settled is the plumbing, then
the wording — never the verdicts. **Nobody has yet read whether a judgement is RIGHT**, which
is where reading matters most: neither the suite nor a self-agreement rate can tell, only that
a verdict was asked, quoted and labelled correctly, and that repeats of it agree. A criterion
can be perfectly stable and stably wrong.

Three kinds of finding come out of such a review and they have different destinations, so
it is worth separating them while reading: *the model extracted or judged badly* → the
prompt → a bump of the assessor · *the data is right but the verdict is not* → a decision
constant → also a bump of the assessor · *the criterion itself is badly worded* → a bump of
the **instrument**, which is a different artifact and a different act. The first review
already produced two of the third kind, and they are `course-drafts-qa` v4.

**Not needed for that, needed for a study:** the dry run accepts drafts and requires no
ratification, but a **persisted** judgment does (ADR-0019), and each version of
`drafts-hybrid` is a new identity that inherits nothing from the previous one's
ratification — which is the point of a bump. So **no semantic or judged criterion of this
lineage has yet produced a persisted judgment**, and doing so is one button on
`/admin/assessors` (below) or, unchanged, `ratify-assessor --name drafts-hybrid --version 10
--instrument-version-id <version> --email <admin>`. Which version is part of the act: the
registry's current artifact is **v10** (reasoning disabled in both fields; degeneration and
budget cuts each buy one clean retry; the denied upstreams; the wrapped outcome verb), and
each bump inherited nothing from the previous version's runs. Ratifying before the seven judged
criteria have been read would persist verdicts nobody has checked, which is the one thing
the calibration loop exists to prevent.

**The assessors page (`/admin/assessors`, ADR-0036).** Ratification used to be readable
only from the database and performable only from a terminal, which is what had been
standing between a calibrated hybrid package and a study. The console now answers *who
can judge, and against which version*: assessors grouped by kind — automated by default,
humans optional, both — and, per automated package, its coverage plus every version of its
lineage with whether it may judge with it, who decided and when. The automated rows come
from the package registry rather than from the `assessors` table on purpose: a package
nobody has ratified has **no row at all**, and that is exactly the one worth acting on.
The act sits behind a dialog that states what is being committed to — this is what lets
judgments persist, it records an author, nothing undoes it, it does not carry over to a
future version of the assessor, and what it checks is coverage and never quality. When
executed criteria have changed since the last ratified version, the endpoint answers
**409 carrying them**, and the dialog turns into a second step listing each criterion with
the `pass_condition` being confirmed and its own checkbox — the ADR-0019 §3 decision,
taken where it can actually be read, rather than an id retyped from an error message.
Behind both gates there is one use case (`RatifyAssessor` + Identity's
`RegisterAutomatedAssessor`), so the CLI and the console cannot drift; the HTTP handler
lives in `app/platform/ratification_router.py` because the act spans two modules and only
the composition root may name two modules' adapters. Deliberately **not** moved to the
console: `profile-content`, `accept-extraction` and a real `evaluate`, each for a reason
named in the ADR. Deliberately **not built**: un-ratifying.

**The calibration page (`/admin/calibration`).** The dry-run loop no longer requires
chaining CLI commands with UUIDs by hand: the console now has a guided page — pick a
profiled content (profile status joined in; a missing profile shows the exact
`profile-content` command instead of a dead end), pick the instrument version (drafts
included) and the assessor package (with its lineage, coverage counts and an LLM-cost
warning), run, and read the partition chips, the per-criterion table with quotes and
failure modes, the claim statuses and the LLM spend. It sits on `GET
/admin/assessor-packages` (the in-code registry as data — identity and coverage, never
the executors) and on the dry-run, which is **started, not awaited**: `POST
/admin/evaluations/preview` returns a run id (202), `GET
/admin/evaluations/preview/{run_id}` reads it while it advances, and `…/trace` returns
every LLM attempt whole. Same `PreviewEvaluation` use case the CLI wires — accepts
drafts, needs no ratification, **persists nothing** (the response says
`persisted: false`; the suite pins zero writes), and the runs themselves live in memory
(last 20), forgotten on restart. Only the assessor is validated in the request (404);
a missing profile, an unknown instrument version and an `AssessorExecutionError`
(ADR-0034) become the run's own named error, each shown with its remedy.
Deliberately NOT on the page: triggering profiling (a deliberate act,
CLI-only — the profiling module's stance holds) and registering local folders
(`register-package --source <dir>`); registering by http(s) source stays on the Courses
page. `evaluate --dry-run` remains the scriptable path — the page and the CLI share the
same use case, so they cannot drift. The results end with a **fitness preview**: the
ADR-0023 arithmetic (formula v1, same denominator rule) computed locally over the one dry
run, per quality and rolled up per dimension, labelled as an orientation for calibration —
the real fitness stays a per-study read from persisted judgments. The grouping comes from
`GET /admin/reference/qualities` (live `quality → dimension` reference data, on purpose:
the map frozen at publish protects published studies, and a preview is neither).

**Observability of the LLM half (calibration).** Running an instrument against the real
model used to be opaque in three ways at once: a spinner for minutes, no way to see the
prompt a task sent or the raw text it got back, and failures arriving as a toast that
vanished. One stream now answers all three. `app/platform/observability.py` carries one
record per **attempt** — messages as sent, **how the model was sampled** (temperature,
output budget, response format, whether it may reason), raw answer, `finish_reason`, the
upstream provider that served it, tokens and latency — emitted by the transport to whoever
is listening; the run reads it live (a step per executed criterion and per attempt) and
`LLM_TRACE_DIR` writes it as JSONL, one file per run, untruncated. Both doors write one:
the page's runs under their id, `evaluate --dry-run` under `cli-<id>`, which also prints
each step to stderr and the trace path when it ends. None of this re-versions an
assessor: recording an answer does not change which answer arrives (ADR-0034 §1). The
timeout is now `LLM_TIMEOUT_SECONDS` (access, not identity), default unchanged.

**What the traces then found, and why there is a v2.** Four calibration runs, seven LLM
calls, four of them dead the same way: `completion_tokens` clamped at exactly 2048 — the
task's whole budget — and 100 % of it spent on the model's own thinking, `content` empty.
`outcomes_extraction` failed 3 of 3; the successes of `objectives_classification` were
luck (one spent 1663 tokens on a 421-character answer and just fit). **The LLM half of
`drafts-hybrid:1` could never finish a run**, which is what "pending calibration against
the real model" had been hiding. Two things it is *not*: not a provider problem (seven
calls drew seven upstreams, and the same one appears on both sides — DeepInfra answered
in 331 tokens once and reasoned past the limit another time), and not something a retry
fixes (`length` is deterministic, at 25–85 s an attempt). The fix is the budget, in
`drafts-hybrid:2`: `reasoning: {effort: "none"}` and `MAX_OUTPUT_TOKENS` 8000, both
declared in `SOURCE_CONFIG` — and confirmed in the field, twelve calls for twelve answers
(above). Three transport fixes ride along, none of them
re-versioning anything: a 200 that carries the provider's own error (`choices[].error`)
is read as the upstream failure it is and retried by its code instead of looking like an
empty answer; an empty answer at the token limit says which tokens went where and that
retrying will not help; and the trace records `provider` and `finish_reason` on the
failing paths too, which is where they matter. What was still not decided then — the run
aborting whole when a task cannot answer, discarding the structural criteria that already
passed — is now decided: **ADR-0037** (see the failure-isolation entry above).

**Agreed working mode:** branch + PR per block, with branch names and commits that describe
**the change** (feature/fix), never plan stages; Claude commits only inside the working
branches; Marta reviews and merges. Each PR with the full suite green.
(`13-code-qa.md` §8 mentions an old naming scheme — frozen snapshot, not corrected.)

**Experimental-phase convention:** as long as the first **real** published study does not
exist, instrument versions are **disposable** — iterate with cheap versions
(`bump-instrument` → edit → import → publish), deprecate guilt-free, and there is no
compatibility commitment between versions. The full reproducibility commitment starts with
the first study the team publishes over real content, which pins its version. (Local demo
studies published while verifying do not count — the local DB is disposable by design.)

**In progress — widening the instrument (3 PRs, this is the first).** The draft now asserts
about **16 of the 21 qualities** (17 claims / 27 criteria) instead of 5, so that the
instrument is ready for the day an LLM-carrying assessor exists. Of the 16 new criteria,
**none is executable by `structural:1`** — they all derive `not_assessed`, which ADR-0023
keeps out of the fitness denominator, so **the fitness does not move because of them yet**.
They are written to document the demand and to make the backlog visible (ADR-0018).
Landed in the first PR: the calibration corpus (5 frozen packages instead of 2), the new
reference doc `docs/MEASUREMENT.md`, and the quality rename
`instruction-authentic-tasks` → `instruction-authentic-problems`.

Landed in the second: the `LearnpackV1` adapter supplies **5 capabilities instead of 3** —
`course_descriptor` (what `learn.json` declares about the course; `difficulty` is the
closest this format has to a declared level, and it stopped being a workbench-only extra)
and `lesson_assessment_items` (the same components `lesson_activities` counts, kept
verbatim instead of tallied; a course with no items reports `absent`, so a claim about
assessment cannot pass on nothing). Exercise-file detection was hardened: nothing keys on
a filename (one course names its exercises `index.html`/`about_me.html`), images and
internal `solution.hide` companions are excluded by what they are, and a lesson artifact is
now recognised **structurally** — it must sit directly under `exercises/<slug>/`, so a
misclassified package asset can no longer invent a lesson named after its directory.
`ADAPTER_VERSION` went back to `"1"`; that `"1"` is not the original one.

Landed in the third: `structural` executes **9 criteria instead of 7** and abstains from
the other 18. `cr-lesson-type-matches-delivery` checks the declared lesson type against the
exercise files actually shipped, **in both directions** — the corpus holds one package that
declares practice and ships none, and another that ships exercises in lessons declared as
reading. `cr-no-lesson-spikes-in-lexical-load` is the first criterion decided by a measure:
`lexical_load` (mean syllables per word over prose), compared against the course's own
median, in `structural/measures.py` — its algorithm is part of the assessor's identity, so
changing it is a new assessor even if no criterion's wording moves.
`backend/tests/test_calibration.py` pins what each of the five packages produces, so the
empirical thresholds cannot drift in silence.

**The immediate effect on the fitness:** `learning-progression` stops being blind. Its
audience quality still has no supply, but `progression-cognitive-demand` is now measured
from the lesson bodies, and one defined quality is enough for a dimension to have a value.
**`objectives-quality` is the only dimension left undefined** among those the instrument
covers (`constructive-alignment` has no claims by design).

`constructive-alignment` is **deliberately left with no claim at all**: it compares declared
objectives against content, and LearnpackV1 declares no learning objectives at course or
lesson level. The dimension answers `undefined`, which is the correct answer rather than a
zero. Same for `objectives-specificity`.

**Pending input from the team:** review and edit the draft of the first instrument
(`docs/seed/instruments/learnpack-course-qa-v1.yaml`, written as
assistance; each claim asserts about exactly one quality, ADR-0026) and **publish it**
when the team makes it its own
(`python -m app.cli publish-instrument --id learnpack-course-qa-v1 --email <admin>`,
`POST /admin/instruments/{id}/publish`, or the **Publish** button in `/admin/instruments`, which
confirms before executing). Until then it stays in `draft` — publication is a
human act (12-define, invariant 5). The minted `data_requirement` ids
(`learning_objectives`, `target_audience`, `prerequisites`, `lesson_inventory`,
`lesson_bodies`, `lesson_activities`) are the contract against which the `LearnpackV1`
adapter v2 declares its capabilities — with its `value_domain` declared and
verified (ADR-0020). (The orphan `practice_exercises` was retired by migration `0008`.)

**Runbook for migration `0008`:** it deletes the `data_requirements` rows without a
`value_domain`, so after `alembic upgrade head` the instrument must be imported again
(`import-instrument`) to re-create the namespace; locally `seed-demo` already does it.
Already-persisted profiles are not re-verified against the value domains (a stored profile
is a past fact): to regenerate them, `seed-demo --reset`.

**Runbook for the retired `promptPreprocessor` note (ADR-0030 §4).** `seed-demo` now gives the
demo generator a `changelog` instead, but `_seed_demo_generator` **returns early when the
generator already exists** — seeding never rewrites it. So a dev database seeded before this
change keeps `{"promptPreprocessor": "not versioned yet"}` in `learnpack-generator 1.0.0`, and
the console's Details dialog will show it under *Other metadata*. Two ways out, both fine on a
database that is disposable by design: `seed-demo --reset`, or a hand `UPDATE` of that one row.
Nothing does it automatically, and nothing should: the field is write-once (ADR-0030 §3), so an
automatic rewrite would be the very act the decision withholds.

**Runbook for the renamed quality:** `instruction-authentic-tasks` became
`instruction-authentic-problems` in `docs/seed/pedagogical-reference.yaml`. Two steps, and
any future rename carries the same two.

1. **Run `seed`.** Reference data is **not** touched by `seed-demo --reset`; without this,
   publishing the instrument fails on a quality id that does not exist.
2. **Delete the old row by hand.** Seeding is upsert-by-id and never deletes, so the rename
   leaves the old id behind. Nothing prunes it automatically **on purpose**: a quality can
   be named by a published instrument's frozen `quality → dimension` map, and an automatic
   prune would eat history to tidy a list. Before deleting, check the three things that
   make it safe — no foreign key targets `qualities`, no `instrument_claims.quality_ids`
   names it, and it is absent from every `instrument_versions.quality_dimensions`. On the
   local database all three held and the row is gone; the same check has to be repeated
   wherever else the rename lands.

**And since ADR-0052 that check has a fourth item.** The reference instrument used to store
display names as free text in `criteria.qualities` and reference no quality id at all, which
is why a rename could not reach it. It now stores **the quality id itself**, one per item,
and the item's own `criterion_id` is that same id — so renaming a quality that the reference
elicits means editing `docs/seed/rubric-2.0.0.json` and re-seeding, and the join a validity
coefficient is computed over breaks silently if it is not. Check `criteria.qualities` and
`criteria.criterion_id` alongside the other three before deleting a row.

**Second pending input from the team (block 5):** review the profile samples
(`/admin/profiles` or `app.cli profile-content`) and **accept the extraction** when the team
trusts it (`python -m app.cli accept-extraction --package-format LearnpackV1 --email
<admin>`). Until then, automatic profiling on content registration stays disarmed —
acceptance is a human act (ADR-0012); `seed-demo` auto-accepts it only in local mode.
**Acceptance is per adapter version**, and the version changed with the two new
capabilities, so this act has to be repeated against the current one — an extraction
accepted for the old version says nothing about what the adapter reads now. Since
**ADR-0029** the act arms **both processes**: the API and the CLI wire the same policy list,
so `register-package` auto-profiles exactly like the admin form.

**Third pending input from the team (block 6):** once the instrument is published, **ratify it**
for the first automated assessor (the Ratify button on `/admin/assessors`, or
`python -m app.cli ratify-assessor --name structural
--version 1 --instrument-version-id learnpack-course-qa-v1 --email <admin>` — ADR-0019; the
initial registration is the first ratification) and evaluate with
`python -m app.cli evaluate --content-id <id> --instrument-version-id <id>`. As long as the
instrument stays in draft, the calibration loop is `evaluate --dry-run` (accepts drafts,
persists nothing). `structural:1` executes 9 criteria and abstains from the other 18
(ADR-0018) — its accumulated `not_assessed` are the visible backlog of the LLM assessor, and
each abstention reason names which capability it needs: the **judgment** itself, or only
**extraction/classification**, after which the pass condition is a count or an order check.
The second kind is the cheaper one to build first.

**After block 7 — the generator lineage (ADR-0031).** `GeneratorVersion` was
`{id, name, version}` with the `name` retyped by hand at every registration, so a typo minted a
second generator in silence — a failure no `UNIQUE` can catch, since uniqueness protects against
collision and this is unwanted *distinction*, and a permanent one, since the row is immutable.
The lineage is now its own row: `Generator {id, name}` owns `GeneratorVersion
{id, generator_id, version, metadata}` (migration 0017, with a backfill). Registering a version
selects a parent by id and has no name to misspell; the single remaining act that types a name —
minting a lineage — refuses anything within one or two edits of a registered name and proceeds
only when the caller **echoes that name back** (`confirm_distinct_from` / `--distinct-from`), so a
blind retry cannot pass and no script can carry the override by default. A name differing from a
registered one only in casing or padding is refused outright and is *not* overridable: the store
holds a unique index on `lower(btrim(name))`, the half that survives concurrency. The read side
did not move — the version DTO joins its lineage name, so `GeneratorInfo`, the study report JSON,
the fitness JSON and every screen rendering `{name} {version}` are untouched. Two CLI acts now
exist where there were none (`register-generator`, `register-generator-version`), which is what
the genetic-algorithm loop registers through. The repair act (`rename-generator`) is deliberately
**not built**: published reports freeze the name, so a rename would fix the console and leave the
typo permanent in every report already out — the ADR names the shape it would take.

**Fourth pending input from the team (block 7): sign off the first real study.** The loop is
live end to end: register real contents (the brief arrives mechanically when the package
carries `.learn/initialSyllabus.json`), evaluate them, then
`declare-study → open-study → sign-off-study` (CLI, with the whole selection on the
declaration or corrected later with `update-study`) or the same acts in `/admin/studies`. Signing off the first real study **ends the
disposable-instrument convention** — the pinned version becomes a reproducibility
commitment. Readiness (`/admin/studies/{id}/readiness`) names the gaps beforehand;
matching reports the ADR-0017 unmet demand (objectives/audience/prerequisites have no
LearnpackV1 supply — those claims accumulate `not_applicable` until the generator declares
the data in the package).

## Verified

- **The rater is served the data their items rest on** (suite + by hand over real HTTP,
  ADR-0057). Pinned at all three branches: a **LearnpackV2** course registered and profiled
  from the frozen fixture has its four declaration items asked and `declared` carrying the
  objectives as a list and the audience as a statement, ordered by the first item that rests
  on each; the **V1** demo course has those four withheld and `declared` empty — nothing on
  screen for a question nobody was asked; and a value forced to a shape no screen can read is
  omitted while its item stays asked. Checked end to end against the dev store: the V2 course
  answers **12 asked, 0 withheld**, with three real objectives and "Complete beginners with no
  prior web development experience" reaching the rater. Item 2 now asks what its quality asks
  — the four items whose `required_data` is non-empty carry a pointer back to the block. The
  panel compiles and builds; **nobody has seen it render**.
- **The rubric's content is on a screen, and the preview is the evaluator's own form.**
  `GET /admin/reference/instruments/{id}` returns the whole snapshot — scope, scale, and each
  item with the quality it elicits, what grounds it and the datum it needs — pinned by the
  suite over the seeded rubric, including a 404, a 403, and a draft that reads even though the
  list does not offer it. The preview is `ScoreForm` itself, not a copy: its props are a
  discriminated union, and a preview passed `onSubmit` **fails to compile** (checked by
  compiling one on purpose). It renders in a 460px column because that is the rail the
  evaluator meets it in, not a full-width page. What the comparison already shows: the demo
  assignment is served **8 items with 4 withheld**, against the preview's 12 — which is why
  the preview says every item is shown and a real assignment may hide some. The two pages
  compile and build; **nobody has seen them render** — the browser was not available.
- **The reference instrument was renamed in place, references and all** (suite + migration
  0029 over a populated database). `learnpack-pedagogical-v2` is now
  `learnpack-pedagogical-2.0.0`, named *LearnPack Pedagogical Rubric*; the twelve items, their
  ids and their text are untouched. Applied to the local dev store, its three campaigns came
  across, the twelve criteria followed their version, and an evaluator's pending assignments
  still resolve their instrument. `downgrade` puts the old id back and was run to prove it.
  The window closes with the first reference campaign: after one, the id is answered data.
- **A campaign chooses the reference instrument it pins** (suite + by hand over real HTTP,
  ADR-0056). `GET /admin/reference/instruments` lists the published versions with their scale,
  response format and item count; a **draft** is absent from it and `POST /admin/campaigns`
  refuses it with 422. Exercised against a **second** version, not imagined: a copy of the
  seed with six items instead of twelve, installed with `seed --file`, appears beside the
  seeded one, and a campaign opens against it. `INSTRUMENT_VERSION_ID` is gone, so the class
  of failure that killed the form after ADR-0052 cannot recur. The form and the detail page
  compile and build; **nobody has seen them render**.
- **A campaign is named, and the name is correctable** (suite + by hand over real HTTP,
  ADR-0055). The aggregate refuses a blank name on the way in and on a rename, and a
  **closed** campaign still renames — the decision, pinned at its edge. Over the running
  backend against the dev store: `PATCH /admin/campaigns/{id}` replaces the label and the
  change survives the re-read, a blank name answers 422, an unknown id 404, `CampaignOpened`
  and `CampaignRenamed` both carry the name in the outbox. Migration 0028 was applied to a
  **populated** database, not only a fresh one: the single campaign it found came back as
  `Campaign 9e980bea` — the string the console was already displaying for it. `task db:reset`
  followed by two runs of `task seed:demo` leaves one campaign, *Local demo campaign*, which
  is now the key of that idempotence. The two console pages compile and build; **nobody has
  seen them render** — the standing frontend gap, named here rather than implied.
- **Backend suite green: 1276 tests, 1 skipped** against local Postgres (~90 s). Requires
  `docker compose up -d` in `backend/`; without the DB up, the suite errors, it does not skip.
- **The frontend has no tests and no linter.** `npm run lint` is not runnable — ESLint is not
  installed and `next lint` drops into its interactive setup wizard — and CI runs `tsc
  --noEmit` and nothing else. The enforcement that exists is therefore typing: every palette
  and label map over a domain vocabulary is an exhaustive `Record<Union, …>`, so a seventh
  outcome state or a fourth claim status fails to compile. `npm run build` must be run by hand
  before opening a PR that touches a page: it is the only thing that catches a
  `useSearchParams` outside a Suspense boundary, and CI does not run it.
- **The preview and the criterion record checked against real payloads** (by hand, over the
  development store): key sets match the frontend's types exactly at all three levels —
  document, criterion section and cell — with nothing missing and nothing extra; `publishedAt`
  is absent from the preview; a published study answers `judgmentBasis: publishedReport`; and
  of a real study's 145 cells, **63 passes carry 63 quotes**. `tsc` validates what the frontend
  *believes*: both payloads are `dict[str, Any]` on the backend with no `response_model`, so a
  renamed key would compile and render `undefined`. This check is the substitute, and it is
  manual.
- **The failure budget pinned at both edges and end to end** (suite, ADR-0037 PR 3): a
  failure under the budget becomes `execution_error` carrying `{task, kind, message}`
  while the other criteria and the successes' metrics survive; past the budget the
  executor's own exception propagates and nothing half-derives; an instrument with one
  executable criterion tolerates zero (the ADR-0034 §4 limit case); a registration bug
  propagates even when the budget would have absorbed a typed failure. End to end over
  the frozen course: the evaluation persists, the cause round-trips the repository as
  jsonb, the judgment derives with the claim `insufficient` and `executionError` counted
  in its coverage; over HTTP, a dry run with one failed criterion ends `done` with exact
  coverage around it and its step `ok=false`, and one past the budget ends
  `assessor_failed` with zero writes.
- **The three-way retry pinned on both remedies and the poison case** (suite, ADR-0037
  PR 2): the platform's error taxonomy survives in the raised kind and is never
  clean-retried; an answer cut at the budget raises on one call; a contract never
  satisfied spends its conversation and nothing more; a degeneration is dissolved by a
  clean conversation whose first call carries only system+user, with `clean_retries`
  reported in the task's `llm_*` metric (summed across a vote's samples); a second
  identical degeneration raises after exactly four calls; and a failed shared task is
  memoized — both consuming criteria see the same exception instance with no extra call.
- **The sixth state pinned at every consumer, with nothing yet producing it** (suite,
  ADR-0037 PR 1): the domain validator admits `execution_error` only derived, quoteless and
  carrying its cause, and refuses the cause on every other state; the judgment counts six
  states, leaves the conjunctive rule untouched and **never excludes** a claim for execution
  errors (unlike all-`not_applicable`); the report names `execution_error` as an
  insufficiency cause (never `"unknown"`, `mixed` when combined) and always publishes the
  `executionErrors` caveat; the fitness excludes the state from the denominator, counts it
  in every coverage payload and **raises on an unknown outcome state** instead of dropping
  it silently; the preview API carries `execution_cause`; migration 0018 round-trips the
  cause through the repository.
  **No test touches the LLM network**: the transport contract is pinned over
  `httpx.MockTransport` and the hybrid assessor runs over a fake at the `runtime.get_client`
  seam — prompts, validation, grounding, feedback retries and decision rules run for real.
- **The judged criteria pinned around the verdict, never on it** (suite). The suite cannot
  say whether a verdict is right — that is calibration's job — so it pins everything that
  could break silently: the criterion's own `pass_condition` and its numbered failure modes
  reach the prompt; the answer's shape asks for the reason before the verdict; an evidence
  quote that is not verbatim in the text shown is fed back and, persistent, aborts; a
  failure mode outside the criterion's declared list is refused and re-asked; `cr-arc-character`
  is shown both frame bodies; the two assessment criteria share one mapping (one call, then
  one judgement); the verification judge is shown only the objectives that declare a
  verification AND have an item, and answers a vacuous pass with no call at all when none
  do; the reach count admits only lesson identifiers the plan declares. The frozen
  LearnpackV2 fixture partitions 29 outcomes with 19 executed over **fifteen** calls — five
  judged criteria voted on twice each, two sharing one extraction and two one mapping.
- **Repetition refused in every free-length array** (suite): a reach answer naming one
  lesson twice is fed back and the corrected one lands, and the extraction tasks are issued
  with their own bounded budget.
- **Both bounds pinned** (suite): a judging call is issued with the smaller budget, and an
  answer the provider stopped at the limit raises on the first attempt instead of spending
  the schema budget on a reply that cannot change.
- **The corpora pinned as plain text** (suite): an item whose question contains HTML with
  quoted attributes is shown to the model exactly as the course writes it, and a quote of it
  grounds on the first answer — no retry, no abort. Replayed against the run that died, the
  quote that killed it is refused by the old corpus and accepted by the new one.
- **The evidence ceiling pinned** (suite): an answer over the cap comes back with one
  complaint naming the rule rather than one per entry, and a compliant retry lands; the
  widest legitimate shape seen in the field still passes. Checked against the real
  degenerate answer too, not only over fixtures.
- **The vote and the markdown tolerance pinned** (suite): two agreeing samples settle a
  judgement in two calls and report `agreed 2 of 2`; a split buys a third, the majority wins
  carrying its own side's reason and quote, and the metric says `2 of 3`; the spend reported
  per criterion is the samples summed rather than one of them; and a quote that drops
  `**emphasis**` finds its passage while the stored span keeps the markers the source wrote.
- **The evidence contract pinned on the cases that broke it** (suite): a judgement resting
  on several passages keeps them separate, the first being the result's quote and the rest a
  metric; a quote stitched with an ellipsis is answered with the rule rather than the
  symptom; a quote crossing a line break grounds and is stored **as the source spells it**;
  and an answer repeated verbatim after feedback stops the loop at two calls instead of
  three. Checked against the real failure too, not only over fixtures: the answer that
  killed the second calibration run was replayed through v4 — it now receives the actionable
  message, and all six of the fragments it had stitched ground individually, including the
  three that byte-comparison had rejected over an indent.
- **`drafts-hybrid` pinned end to end** (suite): coverage is a disjoint union over v3's 29
  criteria (and decides v1/v2, so any published version of the lineage can ratify); the
  five semantic executors calibrated on synthetic sequences (falls-back vs consolidation
  dip, flat-at-length, early peak); one extraction shared by paired criteria; a hallucinated quote is fed back and, persistent, aborts; the exact
  29-outcome partition over the frozen LearnpackV2 fixture; ratification stores the
  semantic identity (models + prompts fingerprint) whole.
- **Ratification pinned at both gates** (suite). The CLI tests are untouched and are the
  regression net for the rules having moved into a use case: the same exit codes and the
  same stderr, including `--confirm <id>` and `bump VERSION`. Against the use case
  directly, the delta names each criterion, how it changed, how it was decided and the
  text being confirmed — an abstained one never demands a decision, a criterion the
  coverage does not decide is refused before anyone is asked. Over HTTP: 403 for a
  non-admin, 404 for an unknown package, a 422 per cause (unknown version, draft, foreign
  lineage, undecided criterion, drifted `source_config`) each leaving **no assessor row
  behind**, the 409 carrying exactly the executed criterion that changed with its
  `pass_condition`, and the same call with it confirmed going through. Ratifying twice
  reports that neither the registration nor the ratification happened again, and inserts
  nothing.
- **The registry's ratification state pinned** (suite): a package declared in code lists
  its lineage's versions with no identity row at all; after the act, exactly that version
  flips and carries who and when; a draft is listed and never ratified.
- **The ratification surface checked against the dev database by hand**, not only over
  fixtures: `/admin/assessors` returns both kinds with `kind` set; the registry reports
  the hybrid package and `drafts-structural:1` with no identity row over the three published
  `course-drafts-qa` versions, and `structural:1` ratifying `learnpack-course-qa-v1` (by
  Admin, 08-Aug) — the state STATUS describes, read from the endpoint. The refusals answer
  there too (404 unknown package, 422 unknown version, 422 foreign lineage, 403 for an
  evaluator) and **leave no assessor row behind**. The success path against that database
  was deliberately not taken: ratifying the hybrid package is the team's pending act, and
  there is no un-ratify.
- **Frontend**: typecheck and production build clean, `/admin/assessors` among the built
  routes. The page has **not** been exercised in a browser — no browser was available in
  the session that wrote it, and the repo has no frontend tests. The toggle, the dialog and
  the per-criterion confirmation step are unverified visually.
- **The calibration endpoints pinned** (suite): the registry listing carries coverage and
  `uses_llm` and leaks nothing else; a run over a draft against the frozen course does
  **zero writes** (evaluations, judgments and events counted before and after), the real
  numbering-drift finding comes through executed with its quote, the steps match exactly
  the criteria that were executed, and each way a run can end — missing profile, unknown
  instrument version, an assessor that raises `AssessorExecutionError` (ADR-0034) — ends
  it with its cause named. 403 on both doors, 404 for a run nobody remembers.
- **The trace pinned** (suite): one record per attempt including the retries and the hard
  failures; a 2xx nobody can use leaves its raw body in the record; a broken listener
  never breaks the call; the run's attempts come back whole through `…/trace`, and the
  same records reach the live steps. Frontend typecheck clean.
- **The failures the real runs found, pinned as cases** (suite, over `httpx.MockTransport`
  with the payloads copied verbatim from the traces): a 200 carrying
  `choices[0].error` code 502 retries and the second attempt answers, while one with a
  non-retryable code raises without spending the budget, and either way the record names
  the upstream and its `finish_reason`; an empty answer at the token limit reports the
  reasoning/completion split and is not retried; what an assessor pins as extra wire
  fields reaches the payload and cannot overwrite the model; and `SOURCE_CONFIG` declares
  the sampling that decides all of it.
- **The lineage rules proven both halves** (suite): the near-miss refusal names its candidate,
  a wrong echo is refused again and the right one registers; and against the store alone, two
  lineages differing only in casing or padding cannot coexist. Migration 0017's fold is pinned
  over scratch tables — earliest-declared spelling wins, separator differences are *not* merged,
  and rows that would collide on `(generator_id, version)` are reported instead of merged.
- **The full slice-2 loop tested end-to-end** (suite): register two paired contents (brief
  intake pairs them by hash) → profile → publish an instrument copy → ratify → evaluate →
  declare/pin/compose/open/publish a study → immutable report with the judgment ids
  recorded, the real numbering-drift finding (`05`/`06`) with its quote, generator-level
  distributions with coverage, unknown-generator exclusions, brief completeness and
  abstention causes — and a second publish refused.
- **Attribution proven to be worth something** (suite): a content registered with its
  generator declared unknown is excluded from generator-level accumulation; attributed
  after its study opened, it counts in the report composed at publish and disappears from
  `unknownExclusions`. The one-way rule is tested through the use case and against the
  repository alone (the guard that holds under concurrency).
- **The fitness rules proven on real data** (suite and by hand): over the demo study,
  `objectives-quality` comes back **`undefined`** — LearnpackV1 supplies no objectives, so
  every criterion under it is `not_applicable` and the denominator is 0. A zero there would
  have the GA evolve against a gap in the *package format*, not in the generator.
  It is now the **only** undefined one: `learning-progression` still has no audience supply,
  but `progression-cognitive-demand` is measured from the lesson bodies, and one defined
  quality is enough to give a dimension a value — the point of averaging over *defined*
  qualities rather than scoring the rest zero. `constructive-alignment` does not appear at
  all: the instrument deliberately asserts nothing about it. So **three of the four
  dimensions the instrument covers carry a value**, and the fourth says `undefined` rather
  than being averaged away. `inter-lesson-coherence` is measured from two of its four
  qualities (the numbering-drift `fail` pulling one of them down), and the
  unknown-generator course is counted at study level while excluded from generator level.
- **Manual loop verified in local mode**: `seed-demo --reset` registers the demo courses
  **with intake-derived briefs** (syllabus fixtures in the frozen packages), one linked to
  `learnpack-generator 1.0.0` and one declared unknown → publish + ratify + evaluate both →
  study declared/pinned/composed/opened/published via CLI → `show-report` shows the judgments,
  a populated generator level for the linked course and the other in `unknownExclusions`,
  `promptRecorded: false` per brief, `not_assessed` insufficiencies, the drift finding.
  `attribute-generator` then fills the unknown one and refuses the second attempt.
  `/admin/studies` drives the study acts with a confirm dialog on Publish; `/admin/contents`
  shows brief and generator, offers the attribution on the unknown cell, and narrows the list
  by format and by generator lineage → version (`unknown` being one of the choices) —
  client-side over the list the endpoint already returns whole.
- **Local mode** (ADR-0008) tested end to end: `seed-demo` idempotent and with `--reset`
  (the reset also wipes ratifications, studies and generator versions), `/me` and
  `/dev/identities` responding with `X-Dev-User`, and the frontend compiling **without any
  Clerk key**.
- **Clerk identity end-to-end**: JWT template with `email`/`name`, invite-only, admin and
  evaluator entering with the correct role. The `backend/README.md` runbook has already been run
  in the development environment.
- **Content iframe** (open risk in `docs/design/08-code.md` §8): tested with a real LearnPack
  `consumable_url`, **it embeds fine**. The "open in a new tab" fallback stays because it
  depends on each course's site. A content that declares **no** URL (ADR-0028) renders a
  stated empty state instead of an iframe pointed at nothing — it cannot fall through, since
  an empty `src` resolves to the evaluation page itself and would show a blank recursive
  frame with no explanation.
- **Migration 0015's backfill** run against the local dev store: the two courses registered
  from `courses/` lost their minted `/packages/` URLs (now null), while the `seed-demo`
  `learn-pack.com` declarations and a course registered from a real http source kept theirs.
  Re-running the migration changes nothing. The predicate itself is pinned by the suite over
  five cases, including the two that look like the mount and are not (a deployed host serving
  a `/packages/` path, and a loopback host that is not the mount).

## Open

- **Deploy**: backend to Render, frontend to Netlify, `ALLOWED_ORIGINS` crossed, and repeat the
  Clerk runbook on the production instance. The DB is already Neon.
- **Clerk refuses an address that is already a Clerk user**, and that rule cannot be
  bypassed — so somebody invited in Clerk by hand before this existed gets `delivered: false`
  when invited from the console. The invitation still stands; the remedies are Re-send or
  doing it in Clerk.
- **A JWT template without `email_verified` grants the default role instead of the invited
  one.** The backend cannot detect a misconfigured template, only the login it affects, so it
  logs a warning naming the remedy each time it declines to redeem. An invitation left pending
  for days with the person already signed in is the symptom to look for.
- **No invitation reaches an assessor that already exists**, by design — so somebody who
  signed in before being invited keeps the default role until an admin grants them another
  one from the console.
- **An admin can demote or deactivate every other admin one at a time and then be unable to
  do it to themselves.** The console stays reachable, which is the property the guards
  protect, but the store ends with one admin and no screen that can change it. `set-role` is
  the exit.
- **The declaration a rater reads may be one the learner never sees.** The profile reads the
  package (ADR-0017) and the rater reads the deployment (ADR-0052 §6). ADR-0057 narrows the
  gap — four items are answerable now — but it does not close it: a course whose package
  declares nothing while its processed deliverable states its objectives is still withheld and
  still derived, and a rater shown a declaration the pages never render is being told
  something the learner is not. Both are deliberate; neither is visible on any screen.
- **A draft rubric version is readable but not discoverable.** `/admin/rubrics` lists the
  published versions — it reuses the endpoint ADR-0056 defined as *what a campaign may pin* —
  while the detail endpoint serves any id, draft included. So a draft can be read by typing
  its URL and by no other route. It costs nothing today, because the only thing that writes
  `rubric_versions` is the seed file and its status is `published`; it becomes a real gap the
  moment anything authors a draft.
- **Campaigns pinned to different reference versions are not comparable, and nothing says
  so.** The console now chooses the version each campaign pins (ADR-0056) instead of naming
  one in a constant, so two campaigns can legitimately sit side by side over different
  versions of the reference instrument — different items, possibly a different scale and
  response format. No report refuses to put them in one table, and no screen warns anybody.
  ADR-0056 §5 states the question and deliberately does not answer it.
- **Deactivating somebody leaves their open assignments open.** They will never be answered
  and nothing says so on the campaign screen; cancelling them is a manual act in Campaigns.
- **The last-admin guards are not covered by API tests.** They read the whole store, and the
  suite shares one, so "there is exactly one admin left" cannot be arranged without demoting
  other tests' fixtures. Both are tested at the use-case level over a fake repository.
- **The assessors console was not looked at in a browser.** Types, `npm run build` and the
  backend flows over real HTTP are green; nobody has seen the page render. The frontend has
  no tests, so this is the usual gap, named here rather than implied.
- **Studies that predate the pin stay unpinned, and mixed ones stay mixed.** Migration 0019
  fills the pin only where the answer is unambiguous; a study whose judgments already come
  from two assessors is left null on purpose (ADR-0042 §11 — choosing one afterwards would
  disown half its evidence). Those studies read by recency, as they always did, and say so
  through the `assessor_not_pinned` gap and the `mixedAssessors` caveat. Re-evaluating one
  under a single assessor, or declaring a new study over the same contents, are the two
  exits; neither is automated and neither should be.
- **Studies cannot be deleted or renamed.** No `DELETE` and no `PATCH` anywhere in the app, and
  `purpose` is write-once at declare. A study created and abandoned stays in the list forever.
  It blocks nothing — the console's guided setup was chosen partly so a half-made study is
  never orphaned mid-chain — but the hole is real and a composite create endpoint would have
  needed it.
- **The studies list has no headline column.** Name, status, instrument, counts and date, but
  not "how far along" or a fitness figure, because both need a bulk read that does not exist:
  studies pin different instrument versions, so the count is one query per study. Worth doing
  before any cross-round comparison view, which a sortable column probably makes unnecessary.
- **Composing a report is not batched.** `RegistryGateway.get_contents_by_ids` pulls every
  content snapshot and filters in Python, and the gathering issues one `get_brief` per brief
  and one `get_generator` per generator — about 25 round trips for 20 courses. The console
  fetches the preview on demand and never on a timer, which is the mitigation. Fixing it means
  widening `EvaluandRegistryQueries`.
- **Some pass quotes arrive as serialized JSON.** Seen in the development store now that the
  report shows the evidence behind a pass: a few come back as `["The learner can identify…"]`
  rather than as prose, because the corpus a task quotes from was built with `json.dumps`. It
  is the same class as the escaping defect `drafts-hybrid` v5 fixed for two other corpora — so
  it is **assessor identity, a version bump**, not a report concern, and it is newly visible
  rather than new.
- **The local database ports moved to 15433 (tests) and 15434 (development).** Anyone with an
  existing checkout must update the two URLs in their own `backend/.env`; `docker compose up
  -d` republishes the containers and the named dev volume keeps its data. They were on
  5433/5434, which dodged Postgres's default 5432 and landed on exactly what the Windows
  installer hands a *second* native instance — it scans upward — so a machine with two
  Postgres versions shadowed the container and `localhost` reached the wrong server. It
  presents as `password authentication failed`, never as a refused connection, which reads as
  a credentials problem and is not one; it cost an afternoon twice. `conftest` now stops at
  the door and names the cause. CI is unaffected: it uses 5432 against a service container.
- **Contract change to keep in mind**: the canonical `import-learnpack` JSON uses
  `package_format` (formerly `generating_system`) and takes optional `artifacts` /
  `brief_id` / `edit_provenance` (the dead `metadata` key was dropped — ADR-0017);
  `--base-dir` resolves artifact locators locally. Since ADR-0024 **`generator_version_id`
  is required per entry** (null declares unknown). The slice-1 `--acl` path and
  `to_register_command` **retired with ADR-0027** — anyone scripting it must move to
  `register-package`. `POST /admin/contents` likewise requires the key.
  Since **ADR-0028** `consumable_url` is **optional** on `POST /admin/contents` and in the
  canonical JSON (absent = no deployed instance declared), and `ContentResponse`,
  `ContentPackageResponse` and the evaluator's assignment detail can all return it **null** —
  a client that renders it must handle null. `register-package --consumable-url` is now a
  *declaration*, not an override of a discovered value. Since **ADR-0030**
  `POST|GET /admin/generators/{id}/artifacts` **no longer exist** (404) and the
  `GeneratorArtifactRegistered` event is no longer published — anyone scripting either has
  nothing to move to, by decision. Since **ADR-0031** the generator endpoints are two
  resources: `GET /admin/generators` returns **lineages** `{generator_id, name}` where it used
  to return versions, `POST /admin/generators` takes `{name, confirm_distinct_from?}` and mints
  one, and versions moved to `POST /admin/generators/{generator_id}/versions` and
  `GET /admin/generator-versions` (which answers the old shape plus `generator_id`). A client
  reading the old `GET /admin/generators` breaks; nothing outside this repo's console reads it.
  One error detail is now an **object** rather than a string — the near-miss 409 carries
  `{message, similarTo}`, because the name to echo back is contract, not prose.
  **`POST /admin/evaluations/preview` no longer returns the dry run**: it answers **202
  `{run_id}`** and the result is read from `GET /admin/evaluations/preview/{run_id}`
  (`{status, steps, result, error}`), with the attempts at `…/trace`. The 409 and 502 it
  used to answer are gone — those endings are now the run's `error.kind`
  (`profile_missing` / `assessor_failed`), because a request that returns before the work
  starts cannot report how the work went. Only this repo's console calls it.
  Since **ADR-0036** `GET /admin/assessors` carries `kind` (`human | automated`) and, for
  the automated ones, `automated: {name, version, instrument_id}`; `GET
  /admin/assessor-packages` carries `assessor_id` (null while nothing has ratified the
  package) and `lineage_versions`; and `POST
  /admin/assessor-packages/{name}/{version}/ratify` exists — **409** carries an object
  (`{message, previous_version_id, criteria: [{criterion_id, change, pass_condition}]}`),
  everything else it refuses is a 422 whose `detail` is the cause. All three are additive
  for existing clients.
- **`GeneratorArtifact` retired (ADR-0030).** The entity, the `generator_artifacts` table
  (migration 0016), the event, both endpoints and the console form are gone. It was built
  under the "register yes, extract no" mark and never read by anything: no policy subscribed,
  and its only reader was the list endpoint feeding the form that wrote it. Two reasons beyond
  the unused code — the generator's internals are unverifiable from inside this system and
  belong to the generator team's own versioning, and hand-typed `{kind, locator}` rows are the
  anti-pattern ADR-0027 already removed from the content axis. What replaces it is smaller: the
  admin form now writes an optional **changelog** into the `generator_versions.metadata` blob
  that already existed end to end, and the row's action opens a read-only **Details** dialog
  showing it. The form writes only `changelog`; the endpoint still accepts arbitrary metadata
  and the dialog renders whatever is stored. Rows were dropped, not migrated (no production DB
  yet); historical `events` rows stay, being past facts. `docs/design/09`, `12` and `13` still
  describe the entity — frozen snapshots, superseded by the ADR, not corrected.
- **A vacuous pass is honest and reads badly, and it is not decided which matters more.** Two
  criteria of `drafts-hybrid` pass when there is nothing to judge: `cr-outcomes-observable-verbs`
  when the opening lesson states no outcome, and `cr-objectives-observable-verbs` when the
  course declares no objective. In both, absence is a NEIGHBOURING criterion's finding
  (`cr-outcomes-present`, `cr-objectives-min-count`), each pair evidences one claim whose
  sufficiency is conjunctive, and the claim therefore still fails — the verdict is right and
  the argument has no hole. What is wrong is the reading: the criterion appears in green on
  the per-criterion page quoting an excerpt of the lesson body, because there is no outcome to
  quote. The command-line draft is the first package where this is visible rather than
  theoretical. The alternative is for such a criterion to derive `no_evidence` instead, which
  today an executor cannot express (it answers pass or fail, and `on_missing_evidence` governs
  an absent data requirement, not an empty extraction from a present one). Both criteria would
  have to move together, and it is a bump of the assessor. Deliberately not taken while the
  wrapped-verb bump was being verified: one change, one reading.
- **What is left of the drafts backlog: the nine that read every lesson.** v3 took the seven
  judged criteria answerable without per-lesson fan-out. The nine that remain — the concept
  map (`cr-concepts-introduced-before-use`, `cr-later-lessons-apply-earlier-concepts`), the
  objectives-against-lesson-bodies matrix (three criteria), the per-lesson reads
  (`cr-new-instruction-is-preceded-by-a-problem`, `cr-skill-lessons-carry-a-worked-example`),
  the per-pair bridge and the per-module topic — all take an evaluation from ~10 calls to
  ~40–50. **Three of the nine have been attempted and are back on this list** — the two
  concept-map ones and the per-pair bridge — and what that attempt settled is that the cost
  shape was never the obstacle: answering per unit inside one call carries them for three
  extra calls a course. What it did not settle is what they should ask, which is what
  `dump-concept-touches` is for (above). One of the two things to decide first is now
  decided: **failure isolation is ADR-0037** (a task's failure costs its criteria, not the
  evaluation, bounded by a failure budget — realized in three PRs, the first of which is
  merged). Second, for the
  objectives-against-bodies matrix specifically, whether to decompose it at all: it is a
  **completeness** task, and there is evidence that decomposing those into per-cell
  judgments *loses* to a holistic read, because the decomposition fragments the reasoning
  about what is missing. Worth measuring both ways in calibration rather than assuming.
  `cr-objectives-verb-level-band`'s exit is different and recorded in the abstention
  itself: mint `declared_difficulty` (instrument bump + adapter version + re-acceptance),
  so its absence derives `no_evidence` mechanically instead of forcing a verdict against a
  null anchor.
- **Equal coverage stops being sufficient once criteria are judged.** ADR-0023 §7 lets the
  GA compare fitness only within equal coverage, and coverage is computed by criterion
  **id** — which does not move when a criterion's `pass_condition` is reworded. For a
  code executor that was harmless: the wording changed and the executor kept computing the
  same thing. For a judged criterion the wording **is** the question, so two populations
  with identical coverage may have been asked different things. Nothing is wrong today
  because a study pins exactly one instrument version and cross-study comparison
  (`CompareStudies`) is not built; the condition to add when it is built is **equal
  criterion text**, not merely equal ids. Recorded here because that comparison is the one
  place the omission would be invisible and would silently favour whichever wording is
  easier to satisfy.
- **The provider that serves a model is not pinned, and it decides part of the answer.**
  ADR-0034 §3 puts the transport on the environment side with the rule that it "may alter
  whether and when an answer arrives, never which answer arrives". That rule does not hold
  for a router: OpenRouter picks an upstream per request, two upstreams can serve the same
  model slug at different quantizations (fp8, fp4, int4) without the slug saying so, and the
  backend alone is reported to move benchmark scores by double-digit percentage points. Our
  own traces already show it — the seven calls of a v1 calibration drew seven different
  upstreams. So two evaluations under one assessor identity may have been served by
  different weights, which is the failure ADR-0034 §2 refused to allow for the model id,
  arriving through the next door; it also weakens ADR-0023 §7's equal-coverage rule, since
  two contents in one population can be judged by different weights. **Deliberately not
  fixed here**, because the cheap fix (pin one provider, no fallbacks) buys consistency with
  an availability risk that is worse than the variance right now. The shape when it is
  taken: declare a **quantization floor plus a list of acceptable providers, with fallback
  inside that list**, and decide separately whether that declaration is assessor identity —
  which is an amendment to ADR-0034 and wants its own decision. Nothing is lost by waiting:
  the trace already records which provider answered, so the size of the problem can be
  measured from runs that have already happened.
- **The validity coefficients themselves** (ADR-0015 §4) are still where 13-code §7.2 left
  them: out of the increment, trigger *first reference campaign completed + usable golden*,
  no schema until then. What ADR-0052 changed is that they became **computable** — the human
  score now exists per quality, which is the grain a claim's coefficient needs. Two rules are
  decided and enforced nowhere yet: **a derived score is excluded from the coefficient**
  (ADR-0053 §4 — nobody judged it, so a content whose items were all derived would otherwise
  contribute a perfect agreement no human produced), and a quality whose automated side has
  **no variance** cannot be validated by any number of raters (`progression-prerequisites` is
  the known case: zero violations over every draft judged so far). The second is not a rule
  the code can enforce; it is a check to run over the dataset **before** spending expert
  hours on it.
- **The `absent` branch of the withholding rule has no end-to-end test**, because no frozen
  package in the repo produces one: LearnpackV1 has no capability for those ids at all, and
  the single LearnpackV2 fixture populates both fields. The rule is covered over the snapshot
  and the storage is covered on its own; what is not covered is a real profile with an
  `absent` entry travelling the whole way. A synthetic V2 package would close it.
- **The genetic-algorithm experiment itself.** The fitness it reads exists (ADR-0023, above);
  what does not exist is the loop around it — generating a population, registering and
  evaluating it in bulk, and selecting on the signal. Bulk registration — its first
  bottleneck — is now reduced to dropping course folders under `courses/` and running
  `register-package --all` (ADR-0027, below). Also unbuilt on purpose: comparing fitness
  **across** studies, which needs ADR-0023 §7's equal-coverage rule enforced rather than
  merely published (`CompareStudies`).
- **Pedagogical frames: decided, not built (ADR-0025).** The pedagogical vocabulary becomes an
  explicit entity — a frame owning its dimensions and qualities, declared by each
  `InstrumentVersion` and validated against at publish — and **frames are disjoint namespaces**
  (a quality belongs to one frame; two frames declare similar qualities twice). It is not a
  port: the content axis translates something foreign, the vocabulary only needs scoping. The
  mechanism is built **when a second pedagogical approach actually exists**; until then the
  current 5 dimensions / 21 qualities are the implicit first frame and nothing changes. What
  keeps the door open meanwhile is the `quality → dimension` map frozen in the instrument at
  publish (ADR-0023's need, ADR-0025 clause 4). Cost accepted: no comparability across frames at
  any grain, and ADR-0015 reference data bought per frame.

- **Package intake (ADR-0027): stage 1 complete — CLI/local and form.** Registration by
  discovery is live everywhere: `PackageDiscoveryPort` + the per-format discovery ACL read
  `learn.json` + `.learn/config.json` + `.learn/package-manifest.json`, mint the artifact
  list (the discovery ACL is the **sole writer** of the `kind` vocabulary) and hash the
  fetched bytes into `contents.content_hash` (migration 0014) — re-importing an unchanged
  package is a reported no-op, changed content under the same declared version is refused.
  Local courses live in the gitignored `courses/<name>@<version>/` tree, served by a
  dev-only static mount at `/packages`; that mount is what makes their **artifact locators**
  fetchable, which is all it was ever able to give them. Since **ADR-0028** a local course
  registers with **no consumable URL**: the field declares that a deployed, human-consumable
  instance exists, and dropping a folder into `courses/` deploys nothing (migration 0015
  nulled the minted `/packages/` URLs the earlier rows carried; real declarations, including
  the seeder's `learn-pack.com` courses, are untouched). Automated evaluation does not
  notice — profiles are built from locators, never from this URL; human evaluation is what a
  missing declaration blocks, and the console says so instead of framing a 404.
  `register-package --source <url|dir>` registers
  one, `register-package --all` the whole tree, **`register-package --from-csv <file>` a list
  of URLs**; the seeder registers the demo courses through the same path, declaring their real
  URLs. Both commands **auto-profile** what they
  create once the extraction is accepted, and print what the policy did — until **ADR-0029**
  they never did, because the CLI process subscribed only the evaluation policy while the API
  subscribed four. There is one shared list now. The API side:
  `POST /admin/contents/register-by-source` (http(s) sources; 201 created / 200 unchanged /
  409 content-changed) and `GET /admin/contents/formats`; the admin form registers by
  package URL + generator + provenance — the hand-typed artifact rows are gone, and the
  frontend no longer hardcodes `LearnpackV1`.
  Since **ADR-0035** a local tree no longer has to be `courses/`: `LOCAL_SOURCE_ROOTS`
  declares `key=path` roots, each served under `/sources/<key>` (`courses/` keeps `/packages`
  and its base URL, because the locators registered under it are never rewritten), and
  `/dev/local-courses` — dev-only **and** admin-only, the mode gate on the router so it
  answers 404 before any 401 — browses them, previews and registers. The preview names five
  outcomes per folder: `new`, `new_version` (known course, new bytes, declared version free),
  `unchanged`, `conflict` and `unreadable`. Registration takes **one folder per request**
  (each created course auto-profiles inside it) and refuses when a probe finds the tree is not
  actually served — the locators it writes are permanent. A re-registration cannot repair an
  unknown generator: the hash match returns the existing content untouched and the declared
  generator is discarded, so the response reports `can_attribute_generator` and the attribution
  act stays explicit (ADR-0024). `FilesystemFetcher` now refuses locators outside its base
  directory, which applies to every caller. `/admin/contents/import` drives all of it —
  declare format, generator version and course version, walk the tree, scan, tick the rows,
  register — reachable from a button on `/admin/contents` that only exists in local mode.
  It has no automated tests (the frontend has none at all); the surface underneath is pinned
  by `test_local_courses_dev_api.py`.
  **Measured against the real `datasets/generated` tree, every LearnpackV2 run there scans as
  `unreadable`**: discovery requires `files/course_request.json` and those runs do not carry
  it — the frozen fixture of the same run name does, which is the discrepancy to resolve
  (regenerate, or reopen whether that artifact is hard). One older run fails differently: its
  `lesson_plan.json` declares a lesson `03.1` with no `files/lesson_briefs/03.1.json`.
  **What ADR-0027 and ADR-0028 leave deferred,
  doors open:** stage 2 — **zip upload + storage** (`PackageStoragePort`, filesystem in dev,
  S3-compatible bucket in prod; its own ADR) for packages not hosted anywhere;
  **pull-based batch registration from the LearnPack API** (the `[future]` connected ACL —
  a new root/source for the same `PackageDiscoveryPort` and the same loop, nothing else
  changes); and the **auto re-versioning policy** when the content hash changes under the
  same declared version (today: refused with "declare a new version"; minting the next
  version automatically is a decision not yet taken). The `courses/<name>@<version>/`
  folder convention is provisional and isolated in one CLI function
  (`_generator_for_folder`) — and stays the CLI's: the console declares the generator in its
  form and never reads a folder name. **ADR-0035 adds its own deferrals:** roots added at
  runtime rather than at boot, caching the discovery between scan and register (today the
  package is read twice, and the second read is the authoritative one), and a `--root` flag
  bringing the CLI onto the same roots.

  **A package is no longer read one file at a time.** The enumeration a package declares IS a
  statement that its leaves are independent — not one of them is opened to find another — so
  the discovery says so and `PackageRoot.fetch_all` decides what that costs: a fan-out over
  http, still a loop off a filesystem, where a thread per file would buy a scheduler and no
  time at all. Same split as ADR-0048, in the seam this module already had, so no port was
  injected anywhere and the four callers that build a `PackageDiscovery` are untouched. V1 is
  one wave; V2 is three, and three is what the tree forces — the plan names the lessons, each
  lesson's stats name its body. What did NOT move is pinned: the artifact list is built in the
  declared order and never the order of arrival, the hash is the same package however its root
  read it, one miss among seventy-three still refuses the registration, and a missing syllabus
  is still a state rather than a failure. That fan-out needed a gate first, since
  `all_at_once` caps nothing on purpose: **`HTTP_MAX_CONCURRENCY` (8)** now sits beside the
  shared client, so it bounds every artifact fetch whoever asked for it. Lower than the LLM's
  sixteen for a reason that is not capacity — there the account is ours and the transport backs
  off on 429, here the origin is somebody else's course server, nothing backs off, and a fetch
  that fails refuses the whole registration. Which is also what a wrong ceiling would look
  like: a course that used to register and now does not, indistinguishable from a broken
  package. **Measured on a real course** — 39 artifacts on `learn-pack.com`, about half a second
  a request — reading the declared surface went **19.6 s → 4.4 s**, and the curve is flat past
  sixteen (6.4 s at four, 3.2 s at sixteen, 3.1 s at twenty-four, no failure at any of them):
  what is left by then is the three manifests that cannot fan out, since each names the next.
  The default stays at eight because that is one origin and the setting applies to all of them.
  **And then the other half followed, which the first measurement is what identified**:
  profiling re-reads the package inside the same registration and was the bigger of the two at
  9.4 s, so its group reads — the lesson bodies, and V2's stats files — now go out together as
  well, **9.4 s → 2.3 s**, with the extraction returning byte-identical entries. It also reads
  each artifact **once**: counting what V2 actually fetched turned up 30 downloads for 26
  distinct files (`lesson_plan.json` three times, `user_intent` and `course_value` twice), which
  is not an adapter bug — its entry builders are independent on purpose, each citing what it
  reads without consulting the others — so `ProfileContent` wraps the fetcher for the length of
  one extraction rather than coupling them. Scoped by construction: the next extraction gets a
  new instance, and reading each artifact once is now a **format contract**, checked for every
  registered format. **A whole registration is about 8 s against the ~31 s it started at.**
  **And a tired origin is no longer a broken package.** The fetcher had no retries at all, so
  a dropped connection and a package missing an artifact were the same event — tolerable while
  courses were registered one at a time, not once a file of 34 URLs is some two thousand
  requests against somebody else's server. It now runs the policy `llm.py` settled for the
  other transport: back off on connection errors, timeouts and `429/5xx`, honour `Retry-After`,
  jitter so a fanned-out wave does not stampede. Two things are this transport's own. **A miss
  is answered at once and never waited on** — a package saying it carries no syllabus is a 404
  read on every registration (ADR-0022), and making it wait would tax every package that is
  fine; measured against a real origin, an absence costs one request and ~0.5 s. Worth knowing
  when reading that rule: `learn-pack.com` answers **403** for a missing artifact rather than
  404, which is why the retryable statuses are named as a list instead of excepting 404. And
  **the budget is three attempts, not the LLM's four**, because the unit that pays is different
  — there one call is one answer worth waiting for, here one course is dozens of fetches. A
  failure that spent the budget says `(after 3 attempts)`, which is what tells the two causes
  apart in the summary. **Deferred:** a **streak guard** in `_register_sources`, the mirror of
  `TRANSPORT_FAILURE_STREAK` (ADR-0040 §3), for an origin that hangs rather than refuses — the
  timeout dominates there (10 s per attempt), so a whole file would work through it course by
  course. Not built: it needs the registry's exceptions to say which KIND of failure they
  carry, and nobody has met that origin yet.

  **And that speed is what made a generation a single command rather than a run.**
  `register-package --from-csv <file>` registers every course a file names — one format and
  one generator for all of them, the rule `--all` already follows for a tree — and the loop
  underneath is the same `_register_sources` both batches now share. The file is read
  forgivingly (first column, skip a header, blanks, `#`, duplicates, ignore the columns a
  spreadsheet put beside the URL) and refuses only what it would register wrong: an entry
  that is not http(s). Everything that would fail for every row fails **before the first
  fetch** — the file, the format, the generator — and after that a course that fails is one
  line of the summary. The generator is declared by id or by `--generator-name` +
  `--generator-version`: the lineage is resolved and never minted (ADR-0031), the version may
  be minted but only with `--register-new-version`, because unlike `--all` — which reads a
  version off a folder the generator itself named — a typo here would attribute a whole list
  to a phantom version. **Measured on real courses: ~9 s for a new one, ~4.6 s for one already
  registered**, so fifty is roughly seven minutes in the foreground — short enough to sit in
  front of. That is what buys the decision NOT to build the intake run, and the argument is
  narrower than "a run is unnecessary": progress and cancelling are already there, as the line
  per course a terminal prints and the Ctrl-C it answers to, with nothing to undo because each
  course is its own transaction. What **re-running the file** removes is the third thing a run
  exists for — outliving the process so that *how far did it get* stays answerable. The run
  comes back the day a list has to be started from a browser — CLI-only is the deferral, not an
  oversight. **Two things about it are already settled, so they do not have to be rediscovered
  then:** its worker pool would COPY the caller's context, unlike the batch's, which
  deliberately does not (`platform/concurrency.py` contrasts the two — there is no memoized
  answer to isolate here, and there is a cancellation token to carry); and it wants the mirror
  of `BatchRunRegistry._refuse_overlap` for a different reason, since two runs over one URL race
  on the unique index instead of resolving into the no-op they would be in sequence.

- **Auto-profiling reaches http(s) roots only (ADR-0029).** The policy's fetcher is fixed at
  wiring time, so packages rooted on a filesystem — the seeder's frozen fixtures,
  `import-learnpack --base-dir` — are declined in silence and stay on the manual path
  (`profile-content`/`reprofile --base-dir`, which pick their own fetcher). Letting the fetch
  run instead would commit a `failed` profile that the policy's replay guard then refuses to
  touch: a readable package permanently marked broken by the one path that could not read it.
  **Deferred, doors open:** resolving the fetcher from the **package root** (the ADR-0027 §1
  shape) — that is the recorded exit condition, at which point the guard is *deleted*, not
  generalized; and a **`--no-profile` escape hatch** for bulk registration, **which stopped
  being a real cost**: it was written when each created course paid one fetch per lesson
  *sequentially* inside its post-commit dispatch, so a large tree took minutes with no way to
  opt out. Those fetches go out together now and profiling a course is ~2.3 s against 9.4 s,
  which is inside the noise of registering it at all — the hatch stays deferred because nobody
  is paying for its absence any more, not because nobody got to it. Also noted: `import-learnpack` **without** `--base-dir`
  starts auto-profiling where it did not before (its locators are URLs); benign, but a
  behaviour change. And a second, smaller door: `EventDispatcher.subscribe` appends without
  dedup, so a process that wires twice runs every handler twice — harmless under ADR-0003's
  idempotence requirement, deliberately left loud rather than silently de-duplicated, since
  double wiring is exactly the defect class ADR-0029 §1 exists to prevent.

  **The enforced consumable guard (ADR-0028 §5)** is `[future]`. The admin console *marks* a
  content that declares no consumable URL when composing a campaign, *disables* it with its
  reason in the assign picker, and the evaluator screen states the absence instead of framing
  nothing — but **nothing on the server refuses the assignment**. Enforcing it means
  Orchestration reading the registry inside the assignment path (a port + gateway, the
  ADR-0006 shape), where today `AssignContent` does not consult the registry at all — not
  even to check the content exists. The failure it prevents is visible, reversible and rare:
  the evaluator reads "no deployed instance" and the admin unassigns. Cost accepted: anyone
  bypassing the console — curl, a seeder, a future bulk assigner — can still put a human in
  front of a course that is not deployed anywhere. The door stays open: the field is nullable
  and the port is purely additive.

  **Declaring a consumable URL after registration** is built (ADR-0054, below): the demand
  arrived with ADR-0052 §6, which puts the deployed course in front of an expert while the
  evaluand stays the draft.
- **Generator registration is a prerequisite of generator-level analysis.**
  `learnpack-generator 1.0.0` (SemVer) is registered in the local dev DB and by `seed-demo`;
  **repeat the act in production before registering real content**, so the declaration
  ADR-0024 now demands can name a real generator instead of falling back to `unknown`.
  It is **two acts** since ADR-0031 — `register-generator --name learnpack-generator`, then
  `register-generator-version --generator-name learnpack-generator --version 1.0.0` — and the
  first one is where the spelling is decided for good, since nothing renames a lineage.
  Registering the version is also the moment to write its **changelog** (ADR-0030): the field is
  write-once, so a version registered without one keeps none.
- **Runbook for migration `0017`.** It refuses to run if two `generator_versions` rows fold to
  the same `(lower(btrim(name)), version)` — the message lists them and gives the `UPDATE` /
  `DELETE` to run — because merging them would mean the migration deciding which registration
  was the real one. Rows that fold cleanly (same name modulo casing, different versions) become
  **one** lineage keeping the earliest-declared spelling; the other spellings stop being
  queryable state and survive only inside the `GeneratorVersionRegistered` rows of the outbox.
  On the local dev DB there is a single generator, so the fold is a no-op there. `downgrade`
  goes back **with** its data (the name is derivable from the lineage); what it cannot restore
  is a lineage with no versions, or the spellings the fold discarded.
- **Correcting a generator's declared metadata is `[future]` (ADR-0030 §3).**
  `GeneratorVersion` is immutable and `RegisterGeneratorVersion` is its only writer, so a typo
  in a changelog can only be fixed by registering another version. The repair act has a shape
  already — `attribute-generator`'s (ADR-0024): one-way, actor and time recorded, refusing
  what is already declared, offered at the two gates. It is not built because nobody has
  needed it yet; the door is open, since the column exists and the port would be purely
  additive.
- **Brief completeness (ADR-0022 consequence):** intake-derived briefs carry
  `promptRecorded: false` — pairing holds for "same effective instruction", not for
  attributing differences to prompt wording. Forward ask to LearnPack: persist the
  original prompt in the package (e.g. `courseInfo.originalPrompt`); the intake will pick
  it up through the same channel. Note what that ask is and is not: shipping the prompt is a
  **package format** change (a future `LearnpackV2`), so it says nothing about the courses
  being evaluated today — those keep `promptRecorded: false` forever.
- **Outside the first increment** (named in `13-code-qa.md` §9): loop B operational
  (disputes/defects), annotation queues, per-claim validity metrics, `CompareStudies`.

Out of scope by decision, not for lack of time: assessor calibration, CQRS projections,
outgoing integration events and the connected LearnPack ACL — `[future]`, with the slice 2
design preparing the ground.
