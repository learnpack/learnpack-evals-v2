# ARCHITECTURE — invariantes no negociables

> Estas reglas son **duras**. Todo el código generado debe respetarlas. Si una decisión de
> Define/Code las contradice, gana esta doc (o se cambia esta doc explícitamente primero).

## 1. The Dependency Rule (Clean Architecture)

**Las dependencias de código fuente solo pueden apuntar hacia adentro.** Una capa interna
nunca conoce nada de una capa externa. Nombres, tipos y funciones de las capas externas no se
mencionan en el código de las internas.

```
        outer  ───────────────►  inner      (las dependencias apuntan HACIA ADENTRO)
┌──────────────────────────────────────────────────────────────┐
│ Frameworks & Drivers                                          │
│  FastAPI · Postgres/pgvector · LiteLLM/OpenRouter ·           │
│  Next.js/Tailwind/shadcn · Google Sheets · event bus          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Interface Adapters                                      │  │
│  │  controllers · repository impls · source adapters       │  │
│  │  (HumanExpert / LLMJudge / Deterministic / Hybrid) ·    │  │
│  │  ACLs · event publisher / outbox · read-model projectors│  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │ Application (use cases)                           │  │  │
│  │  │  orquesta el dominio · DEFINE los ports (interfaces)│ │  │
│  │  │  ┌────────────────────────────────────────────┐  │  │  │
│  │  │  │ Domain (entities / value objects)           │  │  │  │
│  │  │  │  Rubric · Criterion · Assessor ·            │  │  │  │
│  │  │  │  Evaluation · ScoringPolicy · domain events │  │  │  │
│  │  │  │  PURO — cero imports de framework           │  │  │  │
│  │  │  └────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

Consecuencias obligatorias:
- **Domain** es Python puro: sin `fastapi`, sin `sqlalchemy`, sin `pydantic` (o solo modelos
  propios), sin `litellm`, sin I/O. Contiene entities, value objects, domain events e
  invariantes.
- **Application** depende solo de Domain. Contiene use cases y **define los ports**
  (interfaces/Protocols) que necesita.
- **Interface Adapters** dependen de Application + Domain. Implementan los ports (repos, source
  adapters, event bus, ACLs) y traducen entre el mundo externo y el modelo.
- **Frameworks & Drivers** es lo más externo (FastAPI, Postgres/pgvector, LiteLLM, Next,
  Sheets). Nada interno los importa.

## 2. Dependency Inversion (ports & adapters)

Los **ports se definen en las capas internas** (Application/Domain); los **adapters se
implementan en las externas**. Ejemplos de ports:
`EvaluationSourcePort` (uno por tipo: Human/LLM/Deterministic/Hybrid), `RubricRepositoryPort`,
`ContentRepositoryPort`, `EvaluationResultRepositoryPort`, `EventPublisherPort`,
`CalibrationStatusPort`. El dominio depende de la abstracción; el adapter concreto
(Postgres, Sheets, LiteLLM) se inyecta desde afuera.

## 3. Aislamiento de módulos (regla horizontal, además de la vertical)

Cada subdominio (ver `03-decompose.md`) es un **módulo** con su propio dominio. Entre módulos:
- Se comunican por **domain events publicados + DTOs de query** (el Published Language de cada
  módulo; ver `05-connect.md`). 
- **Nunca** se importa el dominio interno de otro módulo. Nada de reachar agregados ajenos.
- Los bordes con sistemas externos (LearnPack, providers LLM) pasan por un **ACL** en el
  adapter, que traduce el modelo externo al nuestro.

## 4. Events-first

- El estado evoluciona publicando **domain events**; las *policies* reaccionan (ver
  `02-discover.md`). No hay comandos cruzados entre módulos.
- En el MVP, "publicar un evento" puede realizarse como **append de fila** (Sheets). Los
  eventos son *lógicos*; el contrato no cambia al migrar a un bus real.
- `QualityJudgmentPublished` (y candidatos) pueden convertirse en **integration events**
  salientes vía outbox/relay.

## 5. Contratos y mapeo en los bordes

- Los modelos de dominio **no cruzan** fronteras de módulo ni de capa: se mapean a DTOs.
- La capa de Frameworks traduce request/response ↔ use case input/output; nunca expone
  entities crudas por la API.

## Referencias
`GLOSSARY.md` (lenguaje), `03-decompose.md` (módulos), `05-connect.md` (contratos entre
módulos), `07-define.md` (agregados e invariantes por contexto — en curso).
