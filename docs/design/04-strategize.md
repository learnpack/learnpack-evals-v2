# 04 — Strategize (Core Domain Chart)

> Paso 4 del DDD Starter Modelling Process. Estado: **cerrado (v0, living)**.
> Ejes del chart: diferenciación de negocio (vertical) × complejidad del modelo (horizontal).
> Core = alta diferenciación + alta complejidad (arriba-derecha).

## Clasificación

| Subdominio | Clase | Diferenciación | Complejidad | Nota |
|---|---|---|---|---|
| Pedagogical Evaluation | **Core** | alta | alta | La razón de ser del producto. |
| Rubric Authoring | **Core (secundario)** | alta | alta | Encierra la expertise; su CRUD es fino. |
| Golden Dataset | Supporting | media-alta | media | Ground truth; agregado con reglas. |
| Calibration | Supporting | media (potencial alto) | alta | Valida/sirve al core; **no** es el core. |
| Evaluation Orchestration | Supporting | baja-media | media | Workflow humano necesario. |
| Content Registry | Supporting→Generic | baja | baja-media | Metadata domain-informed. |
| Reporting / Projections | Supporting-generic | baja | baja | Read models. |
| Identity & Access | Generic | baja | baja | Auth off-the-shelf. |
| Notifications | Generic | baja | baja | — |
| Localization | Generic | baja | baja | i18n. |

## Decisión estratégica clave (registrada)

**Core = evaluación pedagógica, NO calibración.** La calibración tiene potencial de
diferenciación, pero se clasifica *supporting* de forma deliberada: valida y sirve al core.
El diferenciador es la *capacidad de producir juicios de calidad confiables, multi-fuente y
multi-criterio*, no el proceso que los valida contra humanos.

## Guía de inversión

- **Modelo de dominio rico, clean architecture, invariantes cuidados:**
  `Pedagogical Evaluation` + el *modelo* de `Rubric Authoring`.
- **Pragmático y fino (good-enough, sin sobre-ingeniería):**
  `Orchestration`, `Golden Dataset`, `Content Registry`, `Reporting`.
- **Comprar / adoptar / trivial:** `Identity`, `Notifications`, `Localization`.

## Implicación para el MVP

El MVP ejercita **casi puro supporting/generic** (`Orchestration` + `Content Registry` +
`Golden Dataset` como meta + `Reporting` de admin + `Identity` simple) con **una rebanada
trivial del core** (el `EvaluationSubmitted` humano y su persistencia). Por eso puede
construirse liviano (incluso sobre Sheets) sin comprometer el core: la parte pesada del core
(fuentes automáticas, métricas, calibración) es toda `[futuro]`.

## Próximo paso
**05 — Connect** (context map + relaciones entre bounded contexts / módulos, y flujos de
domain events / integration events).
