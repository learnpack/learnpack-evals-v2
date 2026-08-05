# ADR-0017 — La superficie declarada del evaluando es el paquete: se retira la content metadata

**Estado:** aceptada · **Fecha:** 2026-08 · **Supersede:** ADR-0001 ·
**Contexto DDD:** Evaluand Registry / Content Profiling

## Contexto

ADR-0001 creó la metadata abierta y tipada por formato (`ContentMetadata` + `MetadataSchema`)
en el slice 1, **antes de que existiera el concepto de paquete**: un contenido era una
`consumable_url` más metadata, y el supuesto era que el ACL de LearnPack alimentaría esos
campos mecánicamente desde su API. Dos cosas cambiaron ese cuadro:

1. El slice 2 introdujo el **`ContentPackage`** (artefactos de kind abierto): el producto
   completo que el generador entrega, del que el extractor deriva evidencia citada
   (ADR-0009). El paquete subsumió el rol de "superficie declarada del producto".
2. El proveedor mecánico de metadata **nunca existió**. En la práctica, lo único que podía
   escribir metadata era una mano humana — y el schema además lo **exigía** (keys required).

El costo se materializó: los primeros cursos reales se registraron con audiencia y
prerequisitos transcritos a mano desde el material del brief, y objetivos **derivados con
IA** — y el instrumento juzgó esa metadata como "el curso declara", convirtiendo defectos
reales del generador en aprobados falsos. Es la inferencia que ADR-0009 prohíbe en el
extractor, entrando por la puerta del registro.

## Decisión

**La superficie declarada del evaluando es el `ContentPackage`. La content metadata se
retira del modelo.**

1. Todo lo que la plataforma o el generador declaren llega como **artefactos del paquete**
   (kind abierto; una URL de API también es un locator fetcheable). No hay canal lateral.
2. Se eliminan `ContentMetadata`, `MetadataSchema`, la tabla `metadata_schemas`, la columna
   `contents.metadata`, el comando `UpdateContentMetadata` con su endpoint y formulario, el
   mapeo de metadata del ACL de LearnPack y el `metadata_view` de las campañas (el panel de
   contexto del evaluador humano — su único uso vivo; los evaluadores juzgan desde el
   contenido mismo).
3. El adapter `LearnpackV1` deja de leer metadata: sus capabilities quedan en lo que el
   paquete real ofrece (`lesson_inventory`, `lesson_bodies`, `lesson_activities`). Los
   data requirements de objetivos/audiencia/prerequisitos **siguen minteados** y los
   criteria **siguen exigiéndolos**: demanda declarada sin oferta.
4. Semántica resultante (12-define inv. 3, segunda mitad): sin capability → sin entrada →
   `not_applicable` → esos claims quedan **fuera del denominador**, registrados en
   coverage; el matching/readiness (13-code §6) reporta la **demanda insatisfecha por
   formato**. El hallazgo "este generador no declara objetivos" se enuncia una vez, al
   nivel sistémico donde es accionable — no como `fail` idéntico repetido en cada curso,
   que no discrimina nada.
5. Evolución prevista: si el generador empieza a declarar estos datos, será un
   `GeneratorVersion` nuevo, el dato estará **en el paquete**, y leerlo será un
   `ADAPTER_VERSION` nuevo que declare la capability — recién entonces "capacidad presente
   + dato ausente ⇒ `absent` ⇒ `fail` por curso" vuelve a ser la semántica correcta.

## Consecuencias

- (+) La contaminación de la superficie declarada se vuelve **imposible por construcción**:
  no existe canal donde una mano humana o una IA externa puedan "declarar por" el curso.
- (+) La semántica de evaluación dice la verdad: claims no evaluables en este formato hasta
  que el generador produzca el dato — visible como cobertura/demanda insatisfecha, nunca
  como aprobado ni como refutación ruidosa (ADR-0011 ya exige reportar cobertura junto al
  resultado).
- (+) Menos superficie: muere una tabla, una columna, un schema con validación, un comando,
  un endpoint y un formulario que solo podían usarse para contaminar.
- (−) `cl-objectives-declared` y `cl-audience-declared` quedan sin evaluar en LearnpackV1
  hasta que el generador declare — es el estado real del mundo, no una pérdida del motor.
- (−) El evaluador humano pierde el panel de contexto de metadata en campañas (tras la
  descontaminación ya estaba vacío). Si el contexto humano volviera a hacer falta, su
  fuente será el paquete/profile, no un campo tipeado a mano.

## Alternativas consideradas

- **Mantener metadata con disciplina** (keys opcionales + hints + regla escrita) →
  rechazada: sin proveedor mecánico, el canal tiene valor presente nulo y riesgo presente
  real; la disciplina depende de memoria institucional.
- **Cerrar solo la puerta de escritura manual** (retirar form/endpoint, conservar el canal
  para un intake mecánico futuro) → rechazada: conserva tabla, schema y validación para un
  rol que el paquete ya cumple; si la plataforma declara algo mañana, se ingiere como
  artefacto.
- **Que el adapter conserve las capabilities de metadata "por si acaso"** → rechazada: una
  capability sin lugar real en el formato produce `absent → fail` uniforme en todos los
  cursos — ruido sin poder discriminante — y oculta que el hallazgo es sistémico, no por
  curso.

## Referencias

ADR-0001 (superseded — su principio "las keys viven en reference data, no en el dominio"
sobrevive en los `data_requirements` de ADR-0014) · ADR-0009 (sin inferencia; la ausencia
es un resultado) · 12-define §Content Profiling inv. 3 (absent ≠ sin entrada; sin capacidad
→ demanda insatisfecha) · 13-code §6 (matching/readiness) · el caso real de contaminación
que originó esta decisión está descrito en el Contexto.
