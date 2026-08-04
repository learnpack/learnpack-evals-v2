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
│  FastAPI · Postgres/pgvector (Neon) · Clerk · LiteLLM/OpenRouter · │
│  Next.js/Tailwind/shadcn · event bus                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Interface Adapters                                      │  │
│  │  controllers · repository impls · assessors             │  │
│  │  automatizados (ADR-0016) · extraction adapters         │  │
│  │  (por PackageFormat) · ACLs · outbox · projectors       │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │ Application (use cases)                           │  │  │
│  │  │  orquesta el dominio · DEFINE los ports (interfaces)│ │  │
│  │  │  ┌────────────────────────────────────────────┐  │  │  │
│  │  │  │ Domain (entities / value objects)           │  │  │  │
│  │  │  │  Instrument (claims·criteria) · Assessor · │  │  │  │
│  │  │  │  Evaluation · ContentProfile · events      │  │  │  │
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
- **Frameworks & Drivers** es lo más externo (FastAPI, Postgres/pgvector, Clerk, LiteLLM,
  Next). Nada interno los importa.

## 2. Dependency Inversion (ports & adapters)

Los **ports se definen en las capas internas** (Application/Domain); los **adapters se
implementan en las externas**. Ejemplos de ports:
`AutomatedAssessorPort` (assessors automatizados — ADR-0016; el camino humano entra por
assignments/UI), `ContentExtractorPort`
(extracción por `PackageFormat`), `DesignAssistancePort` (borradores de claims/criteria),
`InstrumentRepositoryPort` (antes `RubricRepositoryPort`), `ContentRepositoryPort`,
`EvaluationResultRepositoryPort`, `EventPublisherPort`, `CalibrationStatusPort`. El dominio
depende de la abstracción; el adapter concreto (Postgres/Neon, Clerk, LiteLLM, frameworks de
observabilidad/evals) se inyecta desde afuera.

## 3. Aislamiento de módulos (regla horizontal, además de la vertical)

Cada subdominio (ver `design/10-decompose-strategize-qa.md`) es un **módulo** con su propio
dominio. Entre módulos:
- Se comunican por **domain events publicados + DTOs de query** (el Published Language de cada
  módulo; ver `design/11-connect-qa.md`).
- **Superficie pública del módulo:** cada módulo expone su contrato de lectura (*query interface +
  DTOs*), sus eventos, y un proveedor de queries `get_<m>_queries` (para inyectar por `Depends`),
  todo en una `modules/<m>/public.py`. El módulo dueño arma su propio repo **dentro** de ese
  proveedor.
- **Nunca** se importa el dominio interno **ni la `infrastructure`** de otro módulo, ni se nombra
  su repo/adapter concreto. Los módulos ajenos importan **solo** desde la `public.py` del módulo.
- **Regla lint-eable:** ningún import a `modules/*/infrastructure` (ni a `modules/*/domain`) desde
  fuera de ese mismo módulo; única excepción, `platform`/`main` (composition root).
- Los bordes con sistemas externos (LearnPack, providers LLM) pasan por un **ACL** en el
  adapter, que traduce el modelo externo al nuestro.

## 4. Events-first

- El estado evoluciona publicando **domain events**; las *policies* reaccionan (ver
  `design/09-align-discover-qa.md`). No hay comandos cruzados entre módulos.
- En el MVP, "publicar un evento" se realiza como **`INSERT` en la tabla `events`** dentro de la
  misma transacción del agregado (outbox) + dispatch in-process (ADR-0003). Los eventos son
  *lógicos*; el contrato no cambia al migrar a un bus real.
- `QualityJudgmentPublished` (y candidatos) pueden convertirse en **integration events**
  salientes vía outbox/relay.

## 5. Contratos y mapeo en los bordes

- Los modelos de dominio **no cruzan** fronteras de módulo ni de capa: se mapean a DTOs.
- La capa de Frameworks traduce request/response ↔ use case input/output; nunca expone
  entities crudas por la API.

## Referencias
`GLOSSARY.md` (lenguaje), `design/10-decompose-strategize-qa.md` (módulos),
`design/11-connect-qa.md` (contratos entre módulos), `design/12-define-qa.md` (agregados e
invariantes por contexto). Serie histórica del slice 1: `design/01…08` (con banner).
