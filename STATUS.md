# STATUS

_Last updated: 2026-09-01._

**The only place in the repo with dated status**, and the shortest document that can carry it.
It has a **budget**: nothing enters that has a home in an ADR, a test or a PR, and every entry
names the event that deletes it. What was true and stopped being true is **not archived here** —
`git log`, the ADR series and the commit messages are the history, and they are better at it.

| Section | Enters when | Deleted when |
|---|---|---|
| **Where we are** | an area's state changes | the next change replaces it — it never accumulates |
| **Not built on purpose** | a decision defers something | it is built, or an ADR supersedes the deferral |
| **Pending** | known work nobody has started | it ships |

If you find status in any other document — "already done", "X missing", "N tests green",
"verified on such-and-such day" — it is in the wrong file and belongs here.

## Where we are

**Both halves of the system run end to end on a developer's machine. Nothing is deployed.**

**Human evaluation.** A campaign puts courses in front of subject-matter experts, who answer
the reference instrument one item per quality; the result is read **inside that campaign**, at
the grain of the item, and the golden reference is established from coverage. Registering an
evaluator, granting a role and retiring somebody are acts of the console. Exercised end to end
locally; the deploy is the one thing between it and a real panel.

**The course an evaluator opens carries its AI** (ADR-0061), in end to end. The backend holds a
synthetic seat per evaluator on the platform that serves the course and mints a short-lived
session into the frame, so an SME signs in once with Clerk and the exercises and open questions
inside the iframe actually answer. Without the credentials configured the course still loads and
the screen says the AI is unavailable.

**The two halves meet at the claim** (ADR-0063). A campaign qualifies a claim of an assessor
version: over the courses both sides judged, the human 1–5 is cut at ≥4 / ≤2 and compared with
`supported` / `refuted`, and each claim reports its sensitivity and specificity with their
counts, the panel's agreement with itself as the ceiling, and a `tracks | weak | unvalidated`
verdict. Each claim also names the courses where the two sides contradicted each other, with the
experts' answers and comments beside the passage the assessor cited — the reading a weak claim is
rewritten from. It is a read composed on demand, it names the campaign it came from, and no
campaign chosen means no verdict. The thresholds are asserted, not measured: the first campaign
settles them.

**Generator QA.** A study measures the generator versions its recipe names, over a dataset
composed from commissions: each package is discovered and profiled, an instrument's criteria
are judged by an assessor ratified against the pinned version, and the round is signed off into
a frozen report. The fitness projection the optimization experiment reads is derived from the
same outcomes and never enters that report.

**What a set-up store holds** (`docs/seed/workbench.yaml`, ADR-0045):

| | |
|---|---|
| Migration head | `0034` |
| Reference instrument | `learnpack-pedagogical-2.0.0` — 12 Likert items, one per quality |
| Instruments published | `learnpack-course-qa-v1` · `course-drafts-qa-v9` |
| Assessors registered | `structural:1` · `drafts-structural:1` · `drafts-hybrid:13` |
| Extractions accepted | `LearnpackV1` · `LearnpackV2` |

**ADRs 0001–0063 are the decision record** and `docs/README.md` rolls them. The default is that
a decision is realized in the code, so what this file carries is the **exceptions**, below.

## Not built on purpose

Decided, deferred deliberately, and named here so nobody counts on them:

- **The population-rate correction** that a claim's sensitivity and specificity make possible
  (ADR-0063 §9). It needs a randomly sampled campaign and a consumer that asks for it, and it
  enters neither the fitness projection nor a study's frozen report until an ADR says what a
  corrected aggregate means to whoever reads it.
- **Assessor severity.** Unmeasured for the first campaign by choice — and the first suspect if
  its results come out strange.
- **`CompareStudies`**, and with it the dataset-version leg of ADR-0058's comparability gate.
- **Minting a dataset version from what a study measured** — the only permitted direction — and
  the **sample** as a derived read (ADR-0058 §9), with the study-side rename to that word.
- **Anchor courses** in a dataset.
- **Pedagogical frames** (ADR-0025): the vocabulary as a swappable, disjoint namespace.
- **The course title in the frozen study report and in the profiling read model** (ADR-0059).
  The first is deliberate — a frozen record is not a reading surface (ADR-0041) — the second is
  simply not done, so a reader moving between screens meets the same course under two labels.
- **Outgoing integration events.** `QualityJudgmentPublished` and its candidates can leave
  through the outbox; nothing consumes them, so nothing relays them.

## Pending

- **The deploy.** Render + Netlify + Neon + Clerk, once per instance, in the order
  `backend/ENVIRONMENT.md` fixes. It is what stands between the human path and a real panel.
- **The course-session infrastructure** (ADR-0061): an academy, a cohort, a service account and
  its role on the course platform, created once by hand. `backend/.env.example` names the
  variables. Until it exists the evaluator's frame loads the course without its AI.
- **A console for seats.** Provisioning is lazy and needs no screen, but nothing lists which
  evaluators have one, revokes it, or reaps them when a campaign ends.
