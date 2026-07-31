# 05 — Connect (Context Map)

> Paso 5 del DDD Starter Modelling Process. Estado: **cerrado (v0, living)**.
> Objetivo: definir la relación entre bounded contexts / módulos y qué viaja por
> domain events (async) vs. queries de lectura (sync). En el monolito modular, cada
> subdominio = un módulo con su propio event bus lógico.

## Relaciones y mecanismo

| Upstream → Downstream | Patrón | Mecanismo |
|---|---|---|
| Rubric Authoring → Pedagogical Evaluation | Customer/Supplier + Published Language | `RubricPublished` (evento) + `getRubric(version)` (query). Evaluation guarda solo `rubricVersion`. |
| Content Registry → Evaluation / Orchestration | Customer/Supplier (Conformist) | eventos de ciclo de vida + `getContentMetadata(id)` (query). |
| Orchestration ↔ Pedagogical Evaluation | Partnership (bidireccional, events-first) | Orchestration publica assignments (lifecycle propio) y **detecta completitud** (`ContentEvaluationCompleted`) por umbral de submissions; Evaluation publica `EvaluationSubmitted`; Orchestration reacciona (marca la assignment `Submitted`). Sin comandos cruzados. |
| Pedagogical Evaluation → Golden Dataset | Customer/Supplier (subscriber) | suscribe `EvaluationSubmitted`/`ContentEvaluationCompleted` humanos; publica `GoldenReferenceEstablished`. |
| Orchestration → Golden Dataset | Customer/Supplier (subscriber) | Golden suscribe `ContentEvaluationCompleted`; aplica **cobertura** (`coverage ≥ threshold`); publica `GoldenReferenceEstablished`. |
| Golden Dataset + Evaluation(auto) → Calibration | Customer/Supplier (subscriber) | eventos + lectura de ambos result sets → `SourceCalibrated`. `[futuro]` |
| Calibration → Pedagogical Evaluation | Customer/Supplier (provenance) | `SourceCalibrated` (evento) + `getCalibrationStatus(assessor, rubricVersion)`. `[futuro]` |
| (todos) → Reporting | Conformist (projections) | suscriben eventos → read models. |
| Identity → (todos) | Open Host Service (generic) | query de identidad; referencia `assessorId`. |

## Reglas de integración

1. **Default async por domain events** para reacciones / evolución de estado entre módulos.
2. **Query sync de solo-lectura** para "necesito el dato ahora" (nunca escribir cruzando módulos).
3. **Sin comandos cruzados**: un módulo reacciona a eventos, no ordena a otro. (El comando
   inicial entra desde la capa de aplicación/UI al módulo dueño.)
4. **Published Language por upstream** = schemas de eventos + DTOs de query = el contrato
   inter-módulo. Nadie cruza esa frontera de otra forma.
5. Esto es lo que habilita la evolución **modulith → microservicios** sin reescribir contratos.

## Anti-corruption layers (en los adapters del hexágono)

- **LearnPack (`GeneratingSystem`)** en el borde de Content Registry → traduce su modelo a
  `EducationalContent`/`ContentMetadata`.
- **Providers LLM (LiteLLM/OpenRouter)** en el adapter `LLMJudge` de Evaluation → traduce la
  respuesta del provider a `EvaluationResult`. `[futuro]`

## Integration events salientes

`QualityJudgmentPublished` (y quizá `ContentEvaluationCompleted`) son candidatos a publicarse
hacia afuera (LearnPack, reporting externo) vía **outbox/relay** que convierte el evento
interno en llamada API. Patrón "domain events → servicios externos".

## Puente con el MVP sobre Sheets

En el MVP, **"publicar un evento" = agregar una fila** (p.ej. hoja `EvaluationSubmitted`).
Los eventos son *lógicos*, no infraestructura obligatoria. Al cambiar Sheets por store real +
bus, **los contratos entre módulos no cambian** — solo su realización. Aristas MVP:
Content Registry → (Orchestration, Evaluation) → Golden Dataset + Reporting + Identity, todas
realizables como append de filas.

## Próximo paso

**07 — Define** (Bounded Context Canvas + Aggregate Design Canvas por contexto, empezando por
el core `Pedagogical Evaluation`). *06 — Organise* se documenta como placeholder (equipo
chico: un solo equipo/dueño para todos los módulos).
