# ARCHITECTURE — non-negotiable invariants

> These rules are **hard**. All generated code must respect them. If a Define/Code decision
> contradicts them, this doc wins (or this doc is explicitly changed first).

**Five of them are executable**: `backend/tests/test_architecture.py` runs on every `pytest`,
needs no database, and fails with the file and line that broke the rule. Where a rule below is
one of those five, it says so.

## 1. The Dependency Rule (Clean Architecture)

**Source code dependencies can only point inwards.** An inner layer never knows anything
about an outer layer. Names, types and functions of the outer layers are never mentioned in
the code of the inner ones.

```
        outer  ───────────────►  inner      (dependencies point INWARDS)
┌──────────────────────────────────────────────────────────────┐
│ Frameworks & Drivers                                          │
│  FastAPI · Postgres (Neon) · Clerk · httpx (LLM               │
│  transport) · Next.js/Tailwind · event bus                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Interface Adapters                                      │  │
│  │  controllers · repository impls · automated             │  │
│  │  assessors (ADR-0016) · extraction adapters             │  │
│  │  (per PackageFormat) · gateways · ACLs · outbox         │  │
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
- **Domain** is pure Python: no `fastapi`, no `sqlalchemy`, no `pydantic`, no `httpx`, no I/O.
  It contains entities, value objects, domain events and invariants.
  **Executable:** `test_domain_is_pure_python`.
- **Application** depends only on Domain. It contains use cases and **defines the ports**
  (interfaces/Protocols) it needs.
- **Interface Adapters** depend on Application + Domain. They implement the ports (repos, source
  adapters, event bus, gateways, ACLs) and translate between the external world and the model.
- **Frameworks & Drivers** is the outermost layer (FastAPI, Postgres/pgvector, Clerk, httpx,
  Next). Nothing internal imports them.

`app/shared/` holds what every module needs and nobody owns, split by the same layers:
`domain` (ids, the base event, value domains), `application` (`EventPublisherPort`,
`UnitOfWorkPort`) and `infrastructure` (the http/filesystem fetchers). It is not a module — it
owns no aggregate and publishes no events of its own — so the isolation rules of §3 do not
apply to it.

## 2. Dependency Inversion (ports & adapters)

**Ports are defined in the inner layers** (Application/Domain); **adapters are implemented in
the outer ones**. Each module declares its own in `application/ports.py`. Examples of the
kinds:

- **Persistence** — `InstrumentRepositoryPort`, `ContentRepositoryPort`,
  `EvaluationRepositoryPort`, `JudgmentRepositoryPort`, one per aggregate.
- **The outside world** — `ExtractionAdapterPort` (extraction per `PackageFormat`),
  `PackageDiscoveryPort` and `PackageFetcherPort` (reading a package), `BriefIntakePort`,
  `DesignAssistancePort` (claim/criteria drafts).
- **Another module's read side** — `ContentGatewayPort`, `DesignGatewayPort`,
  `EvaluationGatewayPort`, `ProfilingGatewayPort`. See §3.
- **Cross-cutting** — `EventPublisherPort`, `UnitOfWorkPort`, in `app/shared`.

The domain depends on the abstraction; the concrete adapter (Postgres/Neon, Clerk, the LLM
transport) is injected from the outside.

**One seam is deliberately not a port: the automated assessors.** An assessor is a versioned
software artifact whose identity *is* its code (ADR-0016), so it lives in an in-code registry —
`AUTOMATED_ASSESSORS`, keyed by `(name, version)` because that pair *is* the identity — rather
than behind an interface anyone could implement elsewhere. What the application depends on is
the far smaller `Executor` callable each package supplies. Extraction adapters are registered
the same way, one per `PackageFormat`.

## 3. Module isolation (horizontal rule, in addition to the vertical one)

Each subdomain (see `design/10-decompose-strategize-qa.md`) is a **module** that owns its own
domain — where it has one: a supporting read-only module such as Reporting owns no aggregate
and is `application` + `infrastructure` only. Between modules:
- They communicate via **published domain events + query DTOs** (each module's Published
  Language; see `design/11-connect-qa.md`).
- **Module public surface:** a module publishes its read contract (*query interface + DTOs*),
  its events, and a query provider `get_<m>_queries` (to inject via `Depends`), all in a
  `modules/<m>/public.py`. The owning module builds its own repo **inside** that provider.
  A module needs one **if and only if** another module imports it — a leaf nobody consumes is
  not made to write an empty file of ceremony. **Executable:**
  `test_every_consumed_module_publishes_a_public_surface`.
- The internal domain **and the `infrastructure`** of another module are **never** imported, nor
  is its concrete repo/adapter named. Other modules import **only** from the module's
  `public.py`. **Executable:** `test_modules_do_not_reach_into_each_others_internals`.
- **One name, one exception, within a module:** an exception class name is defined **once**
  per module; a refusal two acts share lives in that module's `application/errors.py`, and one
  that belongs to a single act stays with it. `except` matches the class and not the name, so
  a second class with a familiar name is caught by nobody — the refusal escapes its handler
  and leaves as a 500 where the code plainly says 404, with mypy and ruff both green. Across
  modules the same name is fine and sometimes right (Evaluand Registry and Content Profiling
  each have a `ContentNotFound`, meaning different things); the caller that needs both aliases
  one. **Executable:** `test_an_exception_name_means_one_thing_within_a_module`.
- The boundaries with external systems (LearnPack, LLM providers) go through an **ACL** in the
  adapter, which translates the external model into ours.

### Where composition happens

The rules above say a module never reaches into another's internals. Two stronger ones say
*where* the crossing may happen at all, and together they are what keeps a module movable.

- **An application layer imports no other module — not even its `public.py`.** A use case is
  written against its own module's ports and nothing else, so it can be read, tested and moved
  without a second module in scope. **Executable:**
  `test_application_layer_does_not_depend_on_other_modules`.
- **The crossing lives in an adapter, never in an application layer.** It takes three shapes,
  and which one is right follows from who needs the other module:
  - **a use case needs it → a gateway.** `modules/<m>/infrastructure/gateways.py` implements
    that module's own `…GatewayPort` by calling another module's `public.py` and translating
    the answer into local DTOs. The use case sees its port; the other module's vocabulary stops
    at the gateway.
  - **an endpoint needs it → the router composes.** A router is already the outermost layer, so
    it injects the other modules' query surfaces with `Depends` and nothing is inverted for it.
  - **a read model needs it → an infrastructure builder composes.** It takes the foreign query
    surfaces as parameters and aggregates in Python (ADR-0006). This is why Reporting's builders
    sit in `infrastructure/` rather than beside the pure aggregation they call.
- **The composition root is `platform/`, `main.py` and `cli.py`** — the three places allowed to
  name concrete adapters, because wiring them into ports is their whole job. The rules above
  are checked everywhere else.
- **`platform/` also hosts acts that span two modules.** No module may command another
  (§4), so an act that genuinely needs two — ratifying an assessor (Identity + Evaluation),
  starting a batch (Studies + Evaluation) — is composed in the root out of both modules' use
  cases, never by giving one module a handle on the other. Those routers exist for that reason
  alone; everything else routes from its own module.

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
`backend/tests/test_architecture.py` (the five executable rules), `GLOSSARY.md` (language),
`design/10-decompose-strategize-qa.md` (modules), `design/11-connect-qa.md` (contracts between
modules), `design/12-define-qa.md` (aggregates and invariants per context).

Everything under `design/` is a **frozen snapshot**: read one with `adr/` beside it, because
where the two disagree the ADR wins and the snapshot is not corrected. `design/01…08` are older
still — the series that produced the human evaluation path, each carrying a banner that says so.
