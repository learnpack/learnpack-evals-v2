# design — snapshots del proceso de modelado

**Todo lo que hay acá está congelado.** Son los artefactos del DDD Starter Modelling Process
(ddd-crew) y sus insumos: registran **qué pensamos y por qué, en el momento en que lo pensamos**.

Contrato de esta carpeta:

- **No se mantienen.** Si el sistema cambia y contradice a uno de estos documentos, el documento
  **no se corrige**: gana el código y la doc vigente (`../ARCHITECTURE.md`, `../GLOSSARY.md`,
  los READMEs de `backend/` y `frontend/`). Si la contradicción importa, se escribe un ADR.
- **No describen el estado actual.** Para eso está `../../STATUS.md`.
- Se leen para entender **el porqué** de un límite o de un nombre, no para saber cómo está hoy
  el sistema.
- **Supersession:** un cierre del proceso deja su snapshot; la vuelta siguiente lo supersede con
  docs nuevos y un banner en los viejos (mismo modelo que los ADRs).

## Serie vigente — segunda vuelta (ago-2026): QA interno de generadores

| Doc | Pasos | Contenido |
|---|---|---|
| `09-align-discover-qa.md` | Align + Discover | propósito QA interno, tríada de génesis, ECD-lite, los dos bucles, recorrido del usuario, referencia humana en dos capas |
| `10-decompose-strategize-qa.md` | Decompose + Strategize | 9 subdominios, eventos, flujo, líneas de study, core chart, guía de inversión |
| `11-connect-qa.md` | Connect | context map, reglas de integración, queries compuestas (matching/readiness), ACLs, published language |
| `12-define-qa.md` | Define | canvases de los 5 contextos + los 4 por referencia (autocontenido), invariantes, deferrals, marcas de primer incremento |

Decisiones con alternativas: `../adr/0009` … `0015`. Insumos: `research/qa-evals-landscape.md`.

## Serie histórica — primera vuelta (jul-2026): diseño del slice 1 (MVP humano)

**No usar como fuente para código nuevo** (banner en cada doc).

| Doc | Paso | Estado al congelar |
|---|---|---|
| `01-align.md` | Align | cerrado — superseded por 09 |
| `02-discover.md` | Discover | cerrado — superseded por 09 |
| `03-decompose.md` | Decompose | cerrado — superseded por 10 |
| `04-strategize.md` | Strategize | cerrado — superseded por 10 |
| `05-connect.md` | Connect | cerrado — superseded por 11 |
| `06-organise.md` | Organise | placeholder (sigue cierto en espíritu) |
| `07-define.md` | Define | cerrado — superseded por 12 (autocontenido) |
| `08-code.md` | Code (plan del MVP) | cerrado — implementado; el plan del slice 2 será doc propio |
| `research/` | Insumos externos fechados | `deterministic-evaluation-landscape.md` (jul) · `qa-evals-landscape.md` (ago) |
</content>
