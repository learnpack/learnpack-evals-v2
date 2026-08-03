# 09 — Align & Discover (segunda vuelta: QA interno de generadores)

> **Snapshot del diseño vigente (ago-2026)** — cierre de los pasos 1–2 del DDDSMP, segunda
> vuelta (slice 2). Congelado. La verdad siempre-actual vive en `../ARCHITECTURE.md`,
> `../GLOSSARY.md`, `../adr/` (0009–0015) y `../../STATUS.md`. Supersede a `01-align.md` y
> `02-discover.md` (históricos) para todo trabajo nuevo. Serie completa: 09 → 12.

## Align — el encuadre

**Propósito: QA interno de generadores de contenido educativo.** El examinado es **el
generador**; cada contenido es un *work product* suyo. No es señal de mercado ni certificación:
el consumidor es el equipo que produce el contenido.

- **La generación y la regeneración quedan FUERA del sistema.** Entra una `ContentVersion`
  registrada; salen hallazgos accionables. El sistema no observa si sus hallazgos causaron un
  cambio — solo ve aparecer otra versión. Saber si sirvieron = **comparar evaluaciones entre
  versiones**, que sí es capacidad nuestra.
- **Credibilidad = trazabilidad, no independencia.** El modo de falla del QA interno es que el
  equipo ignore el resultado; lo que compra confianza es poder ver la **cita** detrás de cada
  hallazgo y discutirlo (ADR-0009). *(Riesgo diferido: si estas evaluaciones se usaran como
  afirmación hacia afuera, el problema de independencia vuelve entero.)*
- **Entregable: juicio + sugerencias.** Con criteria escritos según ADR-0010 (condición de pase
  + modos de falla), **la falla ya es la sugerencia** — no hace falta motor de recomendaciones.
- **Sin derecho de respuesta ceremonial; sí canal de impugnación de hallazgos** — que alimenta
  la mejora del instrumento, nunca el score del contenido.
- **Acuerdo estadístico por defecto** (raters independientes + dispersión), **escalación por
  umbral**; el primer propósito de la escalación no es resolver el score sino diagnosticar el
  desacuerdo — su salida es **un hallazgo sobre el instrumento**.

### La tríada de génesis (ADR-0012)

| Insumo | Fija | Ejemplo |
|---|---|---|
| **Propósito** | el **alcance**: qué superficie se evalúa | UI/UX fuera — el generador no la controla |
| **Tipo de contenido** | el **objeto**: qué elementos existen y dónde | los instrumentos nacen *para* un `PackageFormat` |
| **Frameworks** | la **norma**: qué debería haber aunque no haya | sin norma, `no_evidence` es imposible |

Regla de alcance: **se evalúa la superficie que el generador controla** (ligada al propósito
actual). Guarda dura: **la demanda jamás se deriva de la oferta observada** — si los criteria
salieran de lo que el contenido tiene, la ausencia dejaría de ser detectable.

### El proceso de diseño (ADR-0013, ECD-lite)

Cadena del argumento evidencial: **claim ← acumulación ← observables ← identificación de
evidencia ← work product**. El diseño corre **hacia atrás**: claims → evidencia → observables →
requisitos de extracción. Cuatro piezas adoptadas: `Claim` como artefacto · **dos granos**
(contenido / generador) · **explicaciones alternativas** por adelantado · **assembly** (cuánta
evidencia basta, por claim). Informe = claims con estatus
`soportado | refutado | evidencia insuficiente`; findings bajo el claim que comprometen.

## Discover — los dos bucles

```
  ⟦ generación / regeneración ⟧          ← FUERA del sistema
              │
   ┌──────────▼───────────────┐    contenido → paquete → perfil (citado) → evaluación →
   │  BUCLE A — evaluar       │    juicio (claims con estatus) → hallazgos
   └──────────┬───────────────┘
              │ desacuerdo · impugnaciones · huecos de cobertura · oferta sin consumidor
   ┌──────────▼───────────────┐    génesis (tipo nuevo → claims → instrumento) +
   │  BUCLE B — instrumentos  │    mejora (diagnóstico → revisión → versión nueva)
   └──────────┬───────────────┘
              └──────────────► vuelve a alimentar el bucle A
```

**Los dos bucles están al mismo nivel:** A produce el valor (juicios/hallazgos); B mantiene la
capacidad (es donde vive el conocimiento de dominio). A sin B degrada; B sin A no tiene contra
qué contrastarse.

### Fases del bucle A

1. **Instrumento listo** — `InstrumentVersionPublished` (pivotal). Diseño según la cadena ECD.
2. **Contenido disponible** — `ContentVersionRegistered`: el **`ContentPackage`** completo
   (consumibles + artefactos internos: manifests, knowledge graph, banco de ítems) + `briefId` +
   `generatorVersionId` + provenance de edición.
3. **Perfilado** — `ContentProfiled` (pivotal, nuevo): evidencia canónica **citada** (ADR-0009),
   por adapter versionado, aceptada por acto humano (`ExtractionAccepted`).
4. **Evaluación** — outcomes tri-estado por criterion, con cita; cobertura exacta; `not_applicable`
   y `no_evidence` derivados mecánicamente (nunca por el assessor).
5. **Hallazgos** — `QualityJudgmentPublished` (claims con estatus + perfil por criterion +
   cobertura) + `FindingRaised` por criterion fallado (cita + sugerencia).

### Bucle B — génesis y mejora

- **Génesis:** tipo de contenido nuevo → perfilar muestras (extras no-canónicos incluidos) →
  enumerar claims → derivar hacia atrás → publicar instrumento *para ese tipo*.
- **Mejora:** `DisagreementDetected` · `FindingDisputed` · `no_evidence` sistemático → diagnóstico
  eligiendo entre las **explicaciones alternativas pre-enumeradas** (+ taxonomía de causas:
  criterion ambiguo · evidencia insuficiente · extractor fallando · conocimiento que cambió ·
  **drift del generador no registrado**) → `InstrumentDefectIdentified` → revisión → versión
  nueva. La autoría de revisiones registra autor + motivo + `assistedBy`.

## El recorrido del usuario (E0–E9) y sus hallazgos estructurales

El recorrido de actividades completo (encargo → registrar generador → inventariar artefactos →
diseñar instrumento → aceptar extracción → componer dataset → ejecutar → confiabilidad antes que
contenido → informe del generador → comparación entre rondas) destapó los conceptos que el
storming no vio; todos incorporados al modelo:

- **`GeneratorVersion`** — identidad **declarada** del examinado (nombre + versión + metadata
  libre); inmutable; distinta config ⇒ otro examinado ⇒ los claims no transfieren (simetría de
  rol con `SourceConfiguration`). `unknown` permitido (excluido de acumulación).
- **`GenerationBrief`** — el encargo de generación con identidad propia: la clave del **diseño
  pareado** entre versiones del generador (mismos briefs, productos nuevos).
- **`ContentPackage`** — el work product multi-artefacto (los artefactos internos suelen ser la
  mejor evidencia). Artefactos a nivel generador: se registran ya, se perfilan demand-driven.
- **`EvaluationStudy`** — la ronda con propósito, gate de confiabilidad y acto de publicación;
  **`StudiesCompared`** = la regresión pedagógica del generador.
- **`ExtractionAccepted`** + versión de adapter en la provenance del perfil.

## Referencia humana (ADR-0015) — dos modos

- **Panel de referencia (capa 1):** SMEs juzgan **qualities directamente**, sin profile,
  elicitación holística. `Rubric v1` se **estabiliza como instrumento de referencia** (no se
  migra). Comprada una vez, reusada contra todas las versiones de instrumento (ancla: las
  qualities — la columna estable del lenguaje).
- **Assessor/verificador (capa 2):** dentro de la ejecución, sobre el profile, verificando
  outcomes citados; **annotation queues** muestreadas (5–10%), priorizadas por desacuerdo.
- Comparación instrumento↔referencia: **coeficientes de validez por claim** (sin sumas);
  techo = inter-rater humano (ADR-0006).

## ADRs de esta etapa

0009 (sin inferencia — evidencia citada) · 0010 (criteria verificables, tri-estado) · 0011 (sin
score único) · 0012 (génesis/tríada) · 0013 (ECD-lite/claims) · 0014 (vocabulario en evidence
models) · 0015 (referencia humana en dos capas). Investigación de respaldo:
`research/qa-evals-landscape.md`.
</content>
