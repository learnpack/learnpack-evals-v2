# ARCHITECTURE — non-negotiable invariants

> These rules are **hard**. All generated code must respect them. If a Define/Code decision
> contradicts them, this doc wins (or this doc is explicitly changed first).

## 1. The Dependency Rule (Clean Architecture)

**Source code dependencies can only point inwards.** An inner layer never knows anything
about an outer layer. Names, types and functions of the outer layers are never mentioned in
the code of the inner ones.

```
        outer  ───────────────►  inner      (dependencies point INWARDS)
┌──────────────────────────────────────────────────────────────┐
│ Frameworks & Drivers                                          │
│  FastAPI · Postgres/pgvector (Neon) · Clerk · LiteLLM/OpenRouter · │
│  Next.js/Tailwind/shadcn · event bus                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Interface Adapters                                      │  │
│  │  controllers · repository impls · automated             │  │
│  │  assessors (ADR-0016) · extraction adapters             │  │
│  │  (per PackageFormat) · ACLs · outbox · projectors       │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │ Application (use cases)                           │  │  │
│  │  │  orchestrates the domain · DEFINES the ports (interfaces)│ │  │
│  │  │  ┌────────────────────────────────────────────┐  │  │  │
│  │  │  │ Domain (entities / value objects)           │  │  │  │
│  │  │  │  Instrument (claims·criteria) · Assessor · │  │  │  │
│  │  │  │  Evaluation · ContentProfile · events      │  │  │  │
│  │  │  │  PURE — zero framework imports              │  │  │  │
│  │  │  └────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

Mandatory consequences:
- **Domain** is pure Python: no `fastapi`, no `sqlalchemy`, no `pydantic` (or only its own
  models), no `litellm`, no I/O. It contains entities, value objects, domain events and
  invariants.
- **Application** depends only on Domain. It contains use cases and **defines the ports**
  (interfaces/Protocols) it needs.
- **Interface Adapters** depend on Application + Domain. They implement the ports (repos, source
  adapters, event bus, ACLs) and translate between the external world and the model.
- **Frameworks & Drivers** is the outermost layer (FastAPI, Postgres/pgvector, Clerk, LiteLLM,
  Next). Nothing internal imports them.

## 2. Dependency Inversion (ports & adapters)

**Ports are defined in the inner layers** (Application/Domain); **adapters are implemented in
the outer ones**. Port examples:
`AutomatedAssessorPort` (automated assessors — ADR-0016; the human path enters via
assignments/UI), `ContentExtractorPort`
(extraction per `PackageFormat`), `DesignAssistancePort` (claim/criteria drafts),
`InstrumentRepositoryPort` (formerly `RubricRepositoryPort`), `ContentRepositoryPort`,
`EvaluationResultRepositoryPort`, `EventPublisherPort`, `CalibrationStatusPort`. The domain
depends on the abstraction; the concrete adapter (Postgres/Neon, Clerk, LiteLLM,
observability/evals frameworks) is injected from the outside.

## 3. Module isolation (horizontal rule, in addition to the vertical one)

Each subdomain (see `design/10-decompose-strategize-qa.md`) is a **module** with its own
domain. Between modules:
- They communicate via **published domain events + query DTOs** (each module's Published
  Language; see `design/11-connect-qa.md`).
- **Module public surface:** each module exposes its read contract (*query interface +
  DTOs*), its events, and a query provider `get_<m>_queries` (to inject via `Depends`),
  all in a `modules/<m>/public.py`. The owning module builds its own repo **inside** that
  provider.
- The internal domain **and the `infrastructure`** of another module are **never** imported, nor
  is its concrete repo/adapter named. Other modules import **only** from the module's `public.py`.
- **Lint-able rule:** no import of `modules/*/infrastructure` (nor `modules/*/domain`) from
  outside that same module; the only exception is `platform`/`main` (composition root).
- The boundaries with external systems (LearnPack, LLM providers) go through an **ACL** in the
  adapter, which translates the external model into ours.

## 4. Events-first

- State evolves by publishing **domain events**; *policies* react (see
  `design/09-align-discover-qa.md`). There are no cross-module commands.
- In the MVP, "publishing an event" is realized as an **`INSERT` into the `events` table** within
  the same transaction as the aggregate (outbox) + in-process dispatch (ADR-0003). Events are
  *logical*; the contract does not change when migrating to a real bus.
- `QualityJudgmentPublished` (and candidates) can become outgoing **integration events**
  via outbox/relay.

## 5. Contracts and mapping at the boundaries

- Domain models **do not cross** module or layer boundaries: they are mapped to DTOs.
- The Frameworks layer translates request/response ↔ use case input/output; it never exposes
  raw entities through the API.

## References
`GLOSSARY.md` (language), `design/10-decompose-strategize-qa.md` (modules),
`design/11-connect-qa.md` (contracts between modules), `design/12-define-qa.md` (aggregates and
invariants per context). Historical series of slice 1: `design/01…08` (with banner).
