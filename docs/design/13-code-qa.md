# 13 — Code (plan de implementación del slice 2: QA interno)

> **Snapshot del diseño vigente (ago-2026)** — paso 8 del DDDSMP, segunda vuelta: el plan de
> código del slice 2, análogo al `08-code.md` del slice 1. **Congelado**: es el plan tal como
> se escribió antes de implementar, no un backlog vivo. En qué punto está el desarrollo hoy →
> `../../STATUS.md`. Reglas duras → `../ARCHITECTURE.md`. Nombres → `../GLOSSARY.md`.
> Serie: 09 → 13. ADRs: 0009–0016.

## Principio rector

El primer incremento del slice 2 es **otra rebanada fina**: el core de a poco con supporting
mínimo (`10-decompose-strategize-qa.md` §implicación) — Design con pocos claims reales · **un**
adapter de extracción (`LearnpackV1`) · Evaluation camino automático mínimo · Studies thin. El
**camino humano legacy (campañas + Rubric v1 + 1–5) queda intacto y funcional** en todo
momento: es la maquinaria del panel de referencia (ADR-0015). Cada bloque termina con la suite
en verde.

Marcas "thin/no" que este plan respeta (12-define §final):
- Port de asistencia: **solo el port** (`DesignAssistancePort` como Protocol); sin adapters LLM.
- `GeneratorArtifact`: registrar sí, extraer no.
- `StudiesCompared`: no (necesita dos rondas).
- Eventos de draft por edición: no (con `InstrumentVersionPublished` alcanza).

---

## 1. Módulos y layout

Convención existente por módulo (probada en el slice 1): `domain/ · application/ ·
infrastructure/` + `public.py` (única superficie importable por otros módulos: constantes de
evento + `<X>Queries` + `get_<x>_queries`). Las reglas de capas y aislamiento son ejecutables
en `backend/tests/test_architecture.py` — los módulos nuevos quedan cubiertos sin cambios.

```
backend/app/modules/
  identity/            # queda; se extiende: assessors automatizados (kind)       §3.1
  evaluand_registry/   # RENAME de content_registry, ensanchado                   §3.2
  evaluation_design/   # RENAME de rubric_authoring, ensanchado (core, bucle B)   §3.3
  content_profiling/   # NUEVO (supporting, ACL interpretativo)                   §3.4
  evaluation/          # queda, reformulado (Pedagogical Evaluation, core)        §3.5
  evaluation_studies/  # NUEVO (supporting, thin deliberado)                      §3.6
  orchestration/       # queda intacto (camino humano, ADR-0002/0005)
  golden_dataset/      # queda intacto
  reporting/           # queda; se retira overall_average/global_average          §3.7
```

## 2. Renames (deuda del glosario) — alcance

**Regla:** se renombra donde el nombre viejo nombra un concepto superseded; se conserva donde
nombra el artefacto `Rubric v1`, que **sigue existiendo con ese nombre** en el glosario
(instrumento de referencia, ADR-0015 — otro artefacto, con otra forma y otras reglas).

| Rename | Alcance |
|---|---|
| `content_registry` → `evaluand_registry` (paquete) | total |
| `rubric_authoring` → `evaluation_design` (paquete) | total (solo 2 imports cruzados) |
| `generating_system` → `package_format` | **total**: columna en `contents`, PK de `metadata_schemas`, constraint `uq_contents_logical_version`, DTOs, API, frontend |
| `rubric_version_id` → `instrument_version_id` | **columnas de tablas compartidas/consumidoras**: `evaluations`, `campaigns`, `content_evaluation_completions`, `golden_references` (+ payloads de evento y API). El id de `Rubric v1` ES un instrument version id |
| `rubric_versions` / `criteria` (tablas) | **se conservan**: almacenan específicamente `Rubric v1` (forma holística 1–5 + anchors, que no se migra) |
| `ContentRegistered` → `ContentVersionRegistered` (evento) | rename; `from_payload` acepta nombres/keys viejos (replay de filas históricas de `events`) |
| `RUBRIC_PUBLISHED` | muere (declarado, nunca emitido); lo supersede `InstrumentVersionPublished` |

**Consecuencia estructural:** las FKs de esas 4 columnas hacia `rubric_versions` **se
eliminan** — la columna contendrá ids de instrumentos nuevos O de `Rubric v1`; la validación
referencial pasa a nivel de app (patrón ya aceptado para referencias cross-módulo). Las FKs
intra-módulo quedan. Los datos existentes en las tablas de rúbrica/evaluación son de prueba y
se borran en la migración.

Todo esto es la **migración `0002`** (renames de columnas/constraints) + find/replace en los
`text()` SQL de repos, `cli.py`, DTOs, routers, tests y frontend.

## 3. Esquema Postgres por agregado (migraciones `0003+`, DDL a mano)

### 3.1 identity — assessors automatizados (ADR-0016)

```sql
alter table assessors
  add column kind text not null default 'human' check (kind in ('human','automated')),
  add column source_config jsonb,          -- {name, version, instrumentVersionId, ...}
  alter column clerk_user_id drop not null; -- automáticos no tienen Clerk
-- upsert por registry en código: una fila por (nombre, versión) de assessor automatizado (§3.5)
```

El dominio ya solo ve `assessorId`; la cadena de provenance queda keyada igual para humanos y
automatizados.

### 3.2 evaluand_registry (ex content_registry)

```sql
generator_versions(id uuid pk, name text not null, version text not null, metadata jsonb default '{}',
                   created_at timestamptz, unique(name, version))          -- inmutable
generation_briefs(id uuid pk, brief text not null, fields jsonb default '{}',  -- campos tipados demand-driven
                  created_at timestamptz)                                   -- inmutable
-- contents se extiende:
alter table contents
  add column brief_id uuid references generation_briefs(id),               -- null = brief ausente (registrado ausente)
  add column generator_version_id uuid references generator_versions(id),  -- null = unknown (excluido de acumulación)
  add column edit_provenance text not null default 'unknown'
    check (edit_provenance in ('pure','human_edited','unknown'));
content_package_artifacts(content_id uuid fk, ord int, kind text, locator text, format text,
                          primary key(content_id, ord))                    -- kind ABIERTO, sin enum
generator_artifacts(id uuid pk, generator_version_id uuid fk, kind text, locator text,
                    format text, registered_at timestamptz)                -- registrar sí, perfilar no
```

Comandos/eventos: `RegisterGeneratorVersion`→`GeneratorVersionRegistered` ·
`RegisterBrief`→`BriefRegistered` · `RegisterContentVersion` (extiende el RegisterContent
actual: paquete + briefId + generatorVersionId + provenance) → `ContentVersionRegistered` ·
`UpdateContentMetadata` (queda) · `RegisterGeneratorArtifact`→`GeneratorArtifactRegistered`.
Queries públicas: `get_content_package` · `get_available_contents(filtros)` ·
`get_generator_version` · `get_brief`.

### 3.3 evaluation_design (ex rubric_authoring)

Conserva las tablas y queries legacy (`rubric_versions`, `criteria`, `RubricSnapshot`) para el
camino humano/panel de referencia. Suma:

```sql
-- reference data del lado norma (seed + minteo raro)
pedagogical_dimensions(id text pk, name text)
qualities(id text pk, name text, definition text not null, dimension_id text fk, grounded_in jsonb)
alter table pedagogical_frameworks add column name text, add column scope_note text;  -- sigue delgado
data_requirements(id text pk, definition text not null, aliases jsonb default '[]',
                  value_domain jsonb, grounded_in jsonb, created_at timestamptz)      -- ADR-0014

-- el agregado Instrument (root = InstrumentVersion; claims/criteria/bindings como filas-VO)
instrument_versions(id text pk,               -- convención '{instrumentId}-{version}' como el slice 1
                    instrument_id text, version text, name text, purpose text not null,
                    status text check (status in ('draft','published','deprecated')),
                    published_at timestamptz, published_by uuid,
                    revision_author uuid, revision_reason text, assisted_by jsonb,
                    unique(instrument_id, version))
instrument_claims(instrument_version_id text fk, claim_id text, ord int,
                  statement text not null,               -- una frase
                  quality_ids jsonb not null,            -- ≥1
                  warrants jsonb not null,               -- framework ids, ≥1 si pedagógico
                  alternative_explanations jsonb not null, -- ≥1 específica del claim
                  sufficiency jsonb not null,            -- §7.1
                  primary key(instrument_version_id, claim_id))
instrument_criteria(instrument_version_id text fk, criterion_id text, ord int,
                    statement text, pass_condition text not null,   -- verificable, legible
                    failure_modes jsonb not null,                   -- la falla ES la sugerencia
                    claim_ids jsonb not null,                       -- qué claims evidencia (≥1)
                    required_data jsonb not null,                   -- data_requirement ids
                    on_missing_evidence text not null default 'no_evidence'
                      check (on_missing_evidence in ('no_evidence','fail')),
                    eligible_sources jsonb not null,               -- valores: human | automated
                    condition jsonb,                                -- criteria condicionales por task variable
                    primary key(instrument_version_id, criterion_id))
instrument_bindings(instrument_version_id text fk, package_format text,
                    task_variables jsonb default '{}',
                    primary key(instrument_version_id, package_format))
```

- **Draft mutable en filas** (update in place); `PublishInstrument` valida las invariantes 2–4
  de 12-define y flippea `status` atómicamente → `InstrumentVersionPublished` (payload = el
  snapshot, 11-connect). Versión nueva = filas nuevas con `claimId`/`criterionId` estables
  (linaje).
- **El instrumento es 100% declarativo** (ADR-0016): no referencia ejecutores ni checks; el
  mapeo criterion→ejecución vive en cada assessor automatizado (§3.5). Los umbrales normativos
  ("al menos 3 objetivos…") viven en la `pass_condition` (ADR-0010).
- **Autoría: archivo + CLI/endpoint, sin UI de autoría.** `import-instrument --file
  <instrument.yaml>` crea/actualiza el draft; `POST /admin/instruments/{id}/publish` (o CLI) es
  el acto humano de publicación. Los "pocos claims reales" del primer incremento se escriben en
  ese YAML con el equipo.
- `MintDataRequirement` ocurre dentro del import/edición (buscar antes de mintear; lint de
  duplicados = test que compara definiciones de ids repetidos). Sin evento propio (sin
  consumidor; queda en la tabla).
- `DesignAssistancePort` se define en `application/ports.py`; sin adapter (thin).
- Queries públicas: `get_instrument(version) → InstrumentSnapshot` (autocontenido: claims +
  criteria + sufficiency + bindings) · `get_data_requirements()` · legacy `get_snapshot`
  (Rubric v1).
- Eventos del primer incremento: **solo** `InstrumentVersionPublished` (+
  `InstrumentDeprecated` cuando haga falta). `ClaimDefined`/`CriterionDefined`/
  `DataRequirementMinted` = eventos de draft → thin/no. `InstrumentDefectIdentified` → bloque
  posterior (§9, "siguiente").

### 3.4 content_profiling (nuevo)

```sql
content_profiles(id uuid pk, content_id uuid fk, package_format text, adapter_version text,
                 status text check (status in ('ok','failed')), error text,
                 profiled_at timestamptz, unique(content_id, adapter_version))  -- coordenadas del root; inmutable
profile_entries(profile_id uuid fk, data_requirement_id text,     -- Conformist: ids del namespace de Design
                value jsonb,
                provenance text not null check (provenance in ('declared_structured','declared_in_content','absent')),
                quote text, locator jsonb,                        -- cita verbatim + ubicación
                primary key(profile_id, data_requirement_id),
                check (provenance = 'absent' or quote is not null))  -- sin cita no es evidencia (ADR-0009)
profile_extras(profile_id uuid fk, name text, value jsonb, quote text, locator jsonb,
               primary key(profile_id, name))                     -- no-canónicos, fuera de contrato
extraction_acceptances(package_format text, adapter_version text, accepted_by uuid,
                       accepted_at timestamptz, primary key(package_format, adapter_version))
```

- **El adapter es infraestructura**: `infrastructure/adapters/learnpack_v1.py` con
  `ADAPTER_VERSION`, `capabilities: set[dataRequirementId]` y `extract(package) → entries`.
  Lee los artefactos del paquete vía un `PackageFetcherPort` (locator → bytes) con impl HTTP e
  impl filesystem (fixtures/local). **La inversión va a fixtures**: paquetes LearnPack reales
  congelados en `tests/fixtures/learnpack_v1/`.
- Comandos: `ProfileContent(contentId)` (manual — funciona sin aceptación: así se producen las
  muestras a revisar) · `AcceptExtraction(packageFormat, adapterVersion)` (admin) ·
  `ReprofileBatch(selección)` (acto explícito, jamás cascada).
- Policy: `ContentVersionRegistered` → perfilado automático **si** hay adapter aceptado para el
  `package_format` → `ContentProfiled` | `ContentProfilingFailed`.
- Invariante 3 de 12-define por construcción: capacidad declarada + dato ausente → entrada
  `absent` explícita; sin capacidad → sin entrada.
- Queries públicas: `get_profile(contentId[, adapterVersion]) → ContentProfileSnapshot` ·
  `get_capabilities(packageFormat)`.

### 3.5 evaluation (reformulado)

```sql
alter table evaluations
  -- rubric_version_id → instrument_version_id ya renombrada en §2
  add column profile_id uuid references content_profiles(id);  -- null en el camino humano/panel (sin profile)
criterion_outcomes(evaluation_id uuid fk, criterion_id text,
                   outcome text not null check (outcome in ('pass','fail','not_applicable','no_evidence')),
                   quote text, locator jsonb, comment text,
                   primary key(evaluation_id, criterion_id),
                   check (outcome not in ('pass','fail') or quote is not null))  -- scored exige cita
computed_metrics(evaluation_id uuid fk, metric_id text, value jsonb not null,   -- filas, no eventos (DP19)
                 primary key(evaluation_id, metric_id))
quality_judgments(id uuid pk, content_id uuid, instrument_version_id text,
                  derived_at timestamptz, coverage jsonb not null)   -- append-only; el más reciente por
                                                                     -- (content, instrument) es el vigente
judgment_claims(judgment_id uuid fk, claim_id text,
                status text check (status in ('supported','refuted','insufficient')),
                evidence_basis jsonb not null,  -- conteos {pass, fail, no_evidence, not_applicable}
                primary key(judgment_id, claim_id))
                -- claim con TODOS sus criteria not_applicable: SIN fila acá (fuera del
                -- denominador — ADR-0011 un nivel arriba); registrado en coverage del judgment
findings(id uuid pk, judgment_id uuid fk, claim_id text, criterion_id text,
         quote text, locator jsonb, failure_mode text not null,      -- el modo de falla ES la sugerencia
         raised_at timestamptz)
```

`criterion_scores` (1–5) queda intacta para el camino humano/panel de referencia.

- **`EvaluateContent(contentId, instrumentVersion, assessorId)`** — el camino automático:
  1. Carga `InstrumentSnapshot` (public de design) y `ContentProfileSnapshot` (public de
     profiling) — prerequisito de profile intacto (ADR-0015).
  2. **Derivación mecánica** (dominio puro, testeable): binding no cubre el formato o
     condicional excluido → `not_applicable` · entrada `absent` → `no_evidence` (o `fail` si
     `on_missing_evidence='fail'`) · resto → lista de "juzgables".
  3. **Assessors automatizados modulares** (ADR-0016): cada uno es un paquete propio en
     `evaluation/infrastructure/assessors/<nombre>/` con `NAME`, `VERSION` y un **mapeo
     interno criterion_id → ejecutor** (código puro hoy; con LLM adentro cuando llegue ese
     adapter — el mecanismo por criterion es detalle interno del assessor, no identidad). Cada
     ejecutor lee el profile y devuelve pass/fail + la cita usada (+ `ComputedMetric`s crudos).
     Cada assessor automatizado **declara su instrumento target** (`instrument_version_id`):
     se debe a los criteria de un instrumento — relación instrumento 1 → 0..N assessors
     automatizados; los humanos no están ligados a ninguno. Un registry en código upserta cada
     (nombre, versión) como fila de `assessors` (§3.1; target en `source_config`) y **valida
     en el registro** que el mapeo cubra todos los criteria del target; `EvaluateContent`
     exige un assessor cuyo target sea el instrumento pedido. Cualquier cambio del assessor ⇒
     versión nueva ⇒ otra identidad. Dos assessors independientes sobre el mismo instrumento =
     el caso de dispersión/acuerdo que ADR-0005 habilita. La consistencia entre `pass_condition`
     (norma) y ejecutor (realización) la verifica la capa 2 humana, no un test.
  4. Persiste evaluation + outcomes + metrics → `EvaluationCompleted`.
- Policy: `EvaluationCompleted` → **derivar judgment**: aplica la sufficiency de cada claim
  (§7.1) sobre los outcomes → inserta `quality_judgments` + `judgment_claims` (estatus + base
  de evidencia) + `findings` (por criterion en fail: cita + failure_mode) →
  `QualityJudgmentPublished` + `FindingRaised`. Claim con todos sus criteria `not_applicable`
  → **excluido de `judgment_claims`**, registrado en coverage. Cobertura exacta tri-estado
  garantizada por construcción (un outcome por criterion del snapshot).
- `DisagreementDetected`: la estructura queda (umbral en la sufficiency), pero con un solo
  assessor automatizado el flujo es inerte en el primer incremento.
  `DisputeFinding`/`FindingDisputed` → bloque posterior (§9, "siguiente").
- Queries públicas batch: `get_judgments(contentIds, instrumentVersion)` · `get_findings(...)`
  · `get_evaluations(...)` (la de scores legacy queda).

### 3.6 evaluation_studies (nuevo, thin)

```sql
studies(id uuid pk, purpose text not null,
        status text check (status in ('declared','prepared','open','published')),
        instrument_version_id text,           -- null en Declared; se fija UNA vez (PinInstrument)
        created_at, opened_at, published_at timestamptz, published_by uuid)
study_recipe(study_id uuid fk, brief_id uuid, primary key(study_id, brief_id))     -- la receta
study_dataset(study_id uuid fk, content_id uuid, primary key(study_id, content_id)) -- materializado al abrir
study_reports(study_id uuid pk fk, report jsonb not null, published_at timestamptz) -- inmutable
```

- Comandos: `DeclareStudy(propósito)` · `PinInstrument` (una vez, antes de abrir) ·
  `ComposeDataset(briefIds → selecciona contentIds de lo registrado)` · `OpenStudy` (dataset
  fijo) · `PublishStudy` (acto humano). `CompareStudies` = **no** en el primer incremento.
- **Sin proyección por suscripción**: al publicar, el report se **compone** vía query ports
  (estilo ADR-0006) — judgments/findings de evaluation, brief/task variables de registry — y
  se materializa inmutable en `study_reports`, **registrando los judgment ids usados**.
  Contenido: por contenido, claims con estatus; a nivel generador, **distribución de estatus
  por claim a través del dataset**; cobertura y caveats **siempre** (evidencia insuficiente,
  exclusiones `unknown`, adapters sin aceptar, desacuerdos). La base de evidencia por claim
  (§3.5) permite calificar cada "insuficiente" con su causa y excluir del denominador los
  claims no aplicables. Nunca agregado cross-claim. Los patrones condicionados por task
  variables se agregan cuando la primera task variable exista (deferral no silencioso).
- Eventos: `StudyDeclared` · `InstrumentPinned` · `StudyOpened` · `StudyPublished`.
- Studies **jamás comanda** a Orchestration; el cableado humano lo hace el actor por UI.

### 3.7 reporting

- **Retirar `overall_average`/`global_average`** de `aggregation.py`, del endpoint
  `/admin/reports/scores`, de la vista admin del frontend y de sus tests (ADR-0011). El
  promedio por criterion entre assessors + dispersión inter-rater quedan (ADR-0006).
- El informe del slice 2 lo sirve `evaluation_studies` (§3.6); reporting no gana piezas nuevas
  en el primer incremento.

## 4. Events-first (sin cambios de mecanismo)

El outbox + dispatcher in-process de ADR-0003 sigue tal cual (`OutboxEventPublisher`,
`EventDispatcher`, `UnitOfWork.commit()` → dispatch post-commit). Los módulos nuevos copian el
patrón de policy existente: traducir `payload` vía `…Fact.from_payload` (Published Language),
transacción propia, idempotencia por inserción condicional (repos que devuelven "recién
insertado"). Payloads camelCase; los `from_payload` de eventos renombrados aceptan los
nombres/keys viejos (replay de filas históricas de `events`).

## 5. Mapeo comando → evento → tablas → policy (nuevo flujo)

| Comando (módulo) | Evento | Escribe | Policy que dispara |
|---|---|---|---|
| RegisterGeneratorVersion (registry) | `GeneratorVersionRegistered` | generator_versions | — |
| RegisterBrief (registry) | `BriefRegistered` | generation_briefs | — |
| RegisterContentVersion (registry) | `ContentVersionRegistered` | contents, content_package_artifacts | (profiling) si hay adapter aceptado → ProfileContent |
| RegisterGeneratorArtifact (registry) | `GeneratorArtifactRegistered` | generator_artifacts | — |
| ProfileContent (profiling) | `ContentProfiled` \| `ContentProfilingFailed` | content_profiles, profile_entries, profile_extras | — (evaluar es explícito en el primer incremento) |
| AcceptExtraction (profiling) | `ExtractionAccepted` | extraction_acceptances | — |
| import-instrument + PublishInstrument (design) | `InstrumentVersionPublished` (payload = snapshot) | instrument_versions, instrument_claims, instrument_criteria, instrument_bindings | — |
| EvaluateContent (evaluation) | `EvaluationCompleted` | evaluations, criterion_outcomes, computed_metrics | (evaluation) derivar judgment |
| — (policy evaluation) | `QualityJudgmentPublished` + `FindingRaised` | quality_judgments, judgment_claims, findings | — (Studies compone on-read) |
| DeclareStudy / PinInstrument / ComposeDataset / OpenStudy (studies) | `StudyDeclared` / `InstrumentPinned` / `StudyOpened` | studies, study_recipe, study_dataset | — |
| PublishStudy (studies) | `StudyPublished` | study_reports | — |

El flujo humano legacy (SubmitEvaluation → quórum → golden) queda exactamente como está.

## 6. Queries compuestas (sin dueño de estado — composición ADR-0006)

Viven en `evaluation_studies` (el consumidor operativo), compuestas vía `public.py` ajenos:

- **Matching:** demanda (`required_data` de un `InstrumentSnapshot`) × oferta
  (`get_capabilities(packageFormat)`) → cobertura esperada + demanda insatisfecha.
  `GET /admin/instruments/{version}/matching?package_format=…`.
- **Readiness:** por study — instrumento pendiente/publicado × matching × `ExtractionAccepted`
  → huecos **por claim** ("claim sin criteria" · "criterion sin dato en este formato" ·
  "extracción no aceptada"). **Informa, no bloquea**. `GET /admin/studies/{id}/readiness`.

## 7. Deferrals de 12-define — decididos por este plan

1. **Sufficiency (ex assembly — el rename es de este plan; ver GLOSSARY):** `sufficiency`
   jsonb por claim, expresado con la taxonomía psicométrica de modelos de decisión:
   - `{"rule": "conjunctive"}` — default y **única implementada** en el primer incremento:
     **soportado** si todos los criteria que evidencian el claim están `scored=pass` ·
     **refutado** si ≥1 está `scored=fail` (un contraejemplo citado refuta) · **insuficiente**
     en cualquier otro caso. Asimetría de error deliberada: el conjuntivo produce falsos
     "refutado" antes que falsos "soportado" — lo correcto para QA interno (el falso refutado
     cuesta una revisión con cita a la vista; el falso soportado esconde un defecto).
   - `existential` y `m_of_n`: vocabulario documentado, **no construido** (demand-driven).
   - **Compensatorio (pesos / promedios / umbral de puntos): prohibido** — ADR-0011 un nivel
     arriba. Gates estilo Quality Matters innecesarios: en el conjuntivo todo criterion ya es
     esencial.
   - **Guía de diseño (lección k12-teacher-skills):** el cuantificador pertenece a la
     `pass_condition` del criterion ("al menos 2 de 3 objetivos…"), no a la sufficiency; un
     claim que parece pedir `m_of_n` es smell de descomposición (¿son dos claims?). Los
     umbrales de acuerdo multi-assessor y `DisagreementDetected` entrarán a este campo cuando
     existan.
2. **Métricas de validez por claim (ADR-0015):** fuera del primer incremento. Trigger: primera
   campaña de referencia completada + golden usable. Sin esquema hasta entonces.
3. **Annotation queues (capa 2):** fuera del primer incremento. Realización prevista:
   reutilizar campañas/assignments de orchestration (12-define lo indica); nada de código
   ahora.
4. **Value domains estructurados:** `data_requirements.value_domain` jsonb opcional, spec
   mínima `{type: string|string_list|number|enum|levels, values?, citation?}` — solo lo que
   los primeros claims consuman.

## 8. CI y modo de trabajo

- `.github/workflows/ci.yml`: backend (ruff check + **mypy estricto scoped a los módulos
  nuevos del slice 2** — el legacy queda excluido explícitamente; su saneamiento es tarea
  futura opcional — + pytest con Postgres como service container; la suite **incluye**
  `test_architecture.py`, que lintea la regla de ARCHITECTURE §3) · frontend (`npm ci` +
  `tsc --noEmit`).
- **Sin import-linter**: sería redundante con los tests de arquitectura ejecutables.
- **Rama + PR por bloque** (`slice2/<nn>-<nombre>`); cada PR se mergea con la suite completa
  en verde — el camino humano legacy queda demostrado intacto en cada paso.

## 9. Orden de implementación por bloques

1. **CI** (§8) — primero, protege todo lo demás.
2. **Renames + deudas** (§2 + §3.7): migración `0002`, paquetes, API/frontend, retiro de
   promedios (ADR-0011), aliases de payload. La suite legacy en verde demuestra el camino
   humano intacto.
3. **Evaluand Registry ensanchado** (§3.2): tablas + comandos + eventos + endpoints admin +
   forms mínimos de admin (generator, brief, contenido con paquete).
4. **Evaluation Design** (§3.3): reference data (seed de dimensions/qualities/frameworks +
   data_requirements) + agregado Instrument + import/publish + `InstrumentSnapshot` +
   invariantes de dominio con tests. Acá se escribe el **primer instrumento real (pocos
   claims)** con el equipo.
5. **Content Profiling** (§3.4): agregado + adapter `LearnpackV1` + fixtures + aceptación +
   policy de perfilado + **visor de profile** (read-only, con citas — la mesa de trabajo del
   diseñador, ADR-0012). Bloques 4 y 5 son paralelizables tras el 3.
6. **Evaluation automático** (§3.5 + §3.1): derivación mecánica + primer assessor
   automatizado + judgment/findings + eventos.
7. **Evaluation Studies thin** (§3.6 + §6): lifecycle + readiness/matching + publicación +
   report + UI mínima (declarar/componer/abrir/publicar + vista del informe).

**Siguiente (fuera del primer incremento):** bucle B operativo (`DisputeFinding`,
`InstrumentDefectIdentified`, diagnóstico) · annotation queues · revisión ligera de Rubric v1
+ primera campaña de referencia · métricas de validez por claim · `CompareStudies`.

## 10. Testing (foco por bloque)

- **Dominio (rico en el core):** invariantes de publicación del Instrument (claims/criteria
  completos, binding ≥1, inmutabilidad post-publish, linaje de ids) · derivación mecánica del
  tri-estado (tabla de casos: capacidad × entrada × on_missing_evidence × condicionales) ·
  sufficiency conjuntiva (incl. exclusión del claim todo-`not_applicable`) · invariantes de
  Study (pin una vez, dataset fijo, publish inmutable).
- **Adapters por fixtures (la inversión de Profiling):** paquetes LearnPack congelados →
  profile esperado exacto, citas incluidas; caso "capacidad sin dato → absent explícito".
- **Assessors automatizados:** validación de registro (cobertura del target) + ejecutores con
  casos por criterion.
- **Policies:** perfilado on-register (con/sin aceptación) · judgment on-completed
  (idempotencia por inserción condicional, patrón existente).
- **E2E API:** happy path del slice — registrar generador/brief/contenido → perfil → publicar
  instrumento → evaluar → study abierto → publicar → report con cobertura y caveats.
- **Arquitectura:** `test_architecture.py` cubre los módulos nuevos sin cambios.
- Convenciones existentes: tests planos en `tests/`, fixtures de conftest (`cleanup` se
  extiende con las tablas nuevas en orden de FK), sin factories formales.

## Decisiones registradas al escribir este plan

Alcance de renames (§2, incl. conservar las tablas de `Rubric v1`) · autoría de instrumentos
por YAML + CLI/endpoint sin UI · assessors automatizados modulares con instrumento target
(**ADR-0016**) · sufficiency con taxonomía psicométrica y compensatorio prohibido (§7.1) ·
base de evidencia por claim y regla del denominador un nivel arriba (§3.5) ·
`QualityJudgment` append-only con judgment ids pinneados en el report (§3.5–3.6) · CI sin
import-linter y mypy estricto scoped a módulos nuevos (§8).

## ADRs relacionados

`0003` outbox (sigue) · `0005` identidad de Evaluation (sigue) · `0006` composición por query
ports (patrón del report y las queries compuestas) · `0009`–`0015` (el diseño que este plan
realiza) · **`0016` assessors automatizados** (nace con este plan).
