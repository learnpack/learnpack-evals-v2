# ADR-0061 — An evaluator reaches the course's AI through a seat we hold

**Status:** accepted · **Date:** 2026-09 · **DDD context:** Course Session (new, generic) ·
Evaluation Orchestration · Evaluand Registry

**Amends ADR-0028**: `consumable_url` is still the declaration that a deployed instance
exists, but it is no longer the string the evaluator's frame is given. The frame is given
that URL with a session appended, minted per request.

## Context

The evaluation screen embeds the course in an iframe pointed at `consumable_url` (ADR-0028),
and the embedding works. What does not work is the half that matters for the campaign: inside
that iframe the AI is off.

LearnPack asks for a session before it will grade an open question, run an exercise or give
test feedback. Without one it shows *"you must login first"* — the course is readable and
nothing else. A subject-matter expert judging a course whose AI never answers is not judging
the course we are asking about; the AI **is** most of what these courses are.

There is no way to switch it on for everybody at once. The prompting endpoint the IDE calls
resolves its token to a real account (`User.objects.get(auth_token=token)`), so a shared, a
service or an anonymous credential is refused there with a 404. The AI is available per human
or not at all.

That leaves three ways to give a human one, and two of them are worse than they look:

- **Ask the SME to sign in to the course platform too.** Two logins, one of them on a
  different product with different branding, for people we are recruiting one at a time and
  who owe us nothing. And it measures a course through an experience no real student has.
- **Use the SME's own account on that platform, where they have one.** Cheapest to describe
  and the most damaging: an evaluator who already exists there ends up in two organisations
  at once, and the code that reads "the user's organisation" picks `members[0]` with no
  deterministic order. Which tenant answers becomes a matter of row order, and one of those
  tenants holds model credentials.
- **Replace Clerk with the course platform's own auth.** Discussed and rejected: it would
  discard the invitation, role and offboarding machinery ADR-0049/0050/0051 already built, and
  we would still have to create an account for every SME.

None of these is about identity in *this* product. Who an evaluator is here — the author of a
judgment, one third of the triple that identifies a result (ADR-0042) — is settled by Clerk
and stays settled by Clerk.

## Decision

**An evaluator consumes the course through a *seat*: a synthetic identity on the course
platform that this backend creates, holds and hands a short-lived session to. The evaluator
never sees it and never signs into it.**

### 1. A seat is a credential elsewhere, not an identity here

`CourseSeat` binds one `Assessor` to one external credential, stored as
`(provider, external_subject)` — the shape migration 0024 settled on for `assessors`, for the
same reason: a column named after a vendor stops being true the moment there are two.

The seat's address and display name are **derived from the assessor's id**, never from the
evaluator's own name or email. Two consequences, both intended: a seat leaks nothing about the
human to another tenant, and no real person can be put in two organisations by us.

Seats are ours to create in bulk, revoke and throw away. Ending a campaign does not touch
anybody's real account anywhere.

### 2. Provisioning is resumable, because it cannot be atomic

Creating a seat is four calls to two services, and no transaction spans them: create the
identity, enrol it, mint a session, register it with the AI service. Only the first is unsafe
to repeat — a second attempt for the same address is refused.

So the row is written as soon as that first call answers, and `enrolled_at` / `ai_enrolled_at`
record the rest as it happens. An interrupted provisioning is **finished**, never restarted. A
seat aggregate that committed only at the end would turn a crash into an identity created over
there that nothing here remembers, and the retry would be refused because the address is taken.

This is why `EnsureCourseSeat` commits more than once, against the convention every other use
case in this codebase follows. The convention assumes the act is one transaction. Here it is
not, and pretending otherwise loses seats.

### 3. Enrolment is not bookkeeping

The seat must belong to a cohort. This looks like an incidental detail of the other platform
and is not: the AI allowance the course page checks is granted to up-to-date students of a
non-SaaS cohort, computed on the fly, and a seat outside one **loads the course and is refused
the moment it asks the AI to run anything**.

Worse, that failure is partial. Open questions never check the allowance, so a seat with no
cohort grades open questions perfectly and fails only on code exercises — which reads like a
broken exercise rather than a misconfigured seat.

### 4. The session travels in the URL, and only there

The course platform reads `?token=` on load and clears it from the address bar. That is the
mechanism it supports, so that is the one used.

The session is minted **per request, in its own endpoint** (`GET /assignments/{id}/course-session`)
rather than carried on the assignment detail. A session is short-lived and specific to one
person; the assignment detail is a description any refetch may serve from cache. Putting the
token there would spread a credential through every cache that ever held an assignment, and
mint one on every screen that reads it — including the ones that never open a course.

Nothing logs the token.

### 5. No session degrades the page, it does not replace it

The endpoint answers **200 with no token** when provisioning fails, and the frame still loads
the course with a strip saying the AI is unavailable and why.

The alternative — a 5xx — trades a course an evaluator can still mostly judge for an error
screen they can do nothing with. The reason carries the provider's own sentence, because
*"this academy is not active"* is something an admin can act on and *"could not create
session"* is not.

The same reasoning applies to configuration: a deployment with no seat credentials boots
normally, every other screen works, and the one screen that needed them says so.

### 6. The seat's organisation holds no model credentials

The session token reaches the evaluator's browser — it has to, the iframe needs it. An
endpoint on the AI service returns the **caller's organisation credentials in the clear**, with
no capability check.

So seats are registered in an organisation that has none, and the completions are paid by the
organisation that owns the prompt templates, which is a different one. Having nothing to hand
out is the containment, and it is why §1's rule that a seat belongs to exactly one
organisation is a security control rather than hygiene.

## Consequences

- (+) The SME signs in once, with Clerk, and the course works — AI included.
- (+) Recruiting stays incremental: seats are provisioned lazily, the first time an evaluator
  opens a course. Nothing has to be prepared per person in advance.
- (+) The login path keeps no dependency on the course platform. `ResolveAssessor` makes no
  outbound call, so an outage over there cannot stop anybody signing in.
- (−) A campaign now depends on infrastructure outside this repo: an academy, a cohort, a
  service account and a role, created once by hand. `backend/.env.example` names them.
- (−) The token is in the iframe's URL. It is short-lived and belongs to a disposable
  identity, but it is visible to anything that can read the frame's src.
- (−) Seats accumulate. Revocation exists on the aggregate; reaping them over there is
  operational work at the end of a campaign.
- (−) The template that grades open questions is owned by an organisation we do not control.
  If its credentials lapse mid-campaign, open questions stop working and nothing here notices
  until an evaluator says so.

## Alternatives

- **A shared service token for everybody** → refused by the provider: the prompting endpoint
  resolves the token to a real account and answers 404 for one that names none.
- **The anonymous public token (passphrase-issued)** → same refusal for the templates that
  matter, plus every completion would be attributed to one synthetic user.
- **The SME's own account on the course platform** → the double-organisation trap of §1, and
  it makes us create accounts under real people's addresses.
- **Replacing Clerk with the course platform's auth** → discards ADR-0049/0050/0051 and still
  requires an account per SME. Rejected before this ADR was written.
- **Pre-provisioning a fixed pool of seats** → considered and dropped once provisioning became
  lazy: a pool needs sizing in advance, which is exactly what recruiting one SME at a time
  cannot give.
