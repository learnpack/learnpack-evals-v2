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

Única excepción viva: **`07-define.md`** sigue abierto — el slice del MVP está cerrado, pero el
diseño táctico del modelo objetivo se sigue completando.

## Contenido

| Doc | Paso | Estado al congelar |
|---|---|---|
| `01-align.md` | Align | cerrado |
| `02-discover.md` | Discover (Big-Picture EventStorming) | cerrado |
| `03-decompose.md` | Decompose (subdominios) | cerrado |
| `04-strategize.md` | Strategize (Core Domain Chart) | cerrado |
| `05-connect.md` | Connect (Context Map) | cerrado |
| `06-organise.md` | Organise | placeholder (equipo chico, un solo dueño) |
| `07-define.md` | Define (Bounded/Aggregate Design Canvas) | **abierto** — MVP completo, modelo objetivo en curso |
| `08-code.md` | Code (plan de implementación del MVP) | cerrado — implementado, ver `../../STATUS.md` |
| `research/` | Insumos externos fechados | cerrado |
