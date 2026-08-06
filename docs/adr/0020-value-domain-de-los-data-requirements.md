# ADR-0020 — La forma de cada dato se declara y se verifica: `value_domain` obligatorio

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Evaluation Design ·
Content Profiling

## Contexto

ADR-0014 le dio **identidad** a los datos que los criteria requieren: ids estables minteados
del lado de la demanda, con definición obligatoria escrita en ese acto, y adapters que
declaran capacidades contra esos ids. El match es por identidad de id, nunca por strings.

Lo que ese ADR no cerró es la **forma**. Hasta acá, qué shape tiene el valor de cada id vivía
solo en la prosa de su `definition` ("as a list where each entry carries the lesson
identifier, slug, position, type and title"). Nada verificaba que lo que un adapter produjo
la tuviera. El contrato se sostenía por coincidencia social: la misma persona escribió el
adapter y va a escribir el assessor.

El riesgo es **estructural**, no una omisión de estilo. Un assessor automatizado se debe a un
**instrumento**, no a un formato de paquete (ADR-0016, refinado por ADR-0019): el mismo
ejecutor corre sobre profiles producidos por cualquier adapter que declare el id que ese
criterion requiere. Un segundo adapter que cubra `lesson_inventory` con otros nombres de
campo produce dos desenlaces, y el peor no es el ruidoso:

1. El ejecutor revienta — profile válido, evaluación caída. Visible.
2. El ejecutor lee `None` donde esperaba un identificador, su parseo falla y el criterion
   emite **`fail` con cita**. Un defecto de generador reportado que nunca existió, entrando
   al judgment y al study, y disputable como "defecto del instrumento" cuando en realidad
   fue un desacuerdo de forma entre dos adapters.

El (2) rompe por debajo la garantía sobre la que está construido el resto del diseño: **sin
cita no es evidencia** (ADR-0009). Una cita correcta sobre un valor mal formado satisface la
letra de esa regla y no su propósito.

La columna `data_requirements.value_domain` existía desde la migración `0005`, viajaba por el
DTO y la parseaba el import — siempre en `null`, sin dueño y sin consumidor. El bloque 6
(evaluación automática) es su primer consumidor real: es el momento en que la forma deja de
ser prosa y pasa a ser una suposición dentro de un ejecutor.

## Decisión

**La forma de cada dato se declara donde se mintea el id, es obligatoria, y se verifica en el
único punto por el que pasan todos los adapters.**

1. **`value_domain` obligatorio en todo `DataRequirement`**, escrito en el mismo acto que la
   `definition` (ADR-0014 cláusula 1): la definición dice qué **significa** el dato, el value
   domain dice qué **forma** toma. Un requisito sin forma declarada no es un requisito válido.
2. **Vocabulario demand-driven** (13-code §7.4), exactamente lo que los ids minteados
   consumen hoy: `string · number · boolean · string_list · record · record_list`.
   `record`/`record_list` llevan `fields` (nombre → domain), con **un nivel de recursión**
   suficiente para el peor caso real (`lesson_activities`).
   - **Campos requeridos sí, campos extra permitidos.** Un `record` declara los campos que
     deben estar y con qué tipo; un campo que la declaración no nombra no es violación. Así
     los dos ejes de versionado quedan independientes: un adapter que empieza a emitir un
     campo más no fuerza una versión nueva del instrumento. El escenario que esta decisión
     defiende sigue cubierto, porque los campos **requeridos** faltarían.
   - **`nullable: true` no es opcionalidad**: el campo debe estar presente y puede ser null.
     Misma disciplina que la invariante 3 un nivel arriba (capacidad declarada + dato ausente
     ⇒ entrada `absent` explícita, nunca fila faltante): un adapter dice "miré y no había
     nada" emitiendo null, no omitiendo la clave. El silencio nunca es evidencia.
   - **Diferido y nombrado, no silencioso:** `enum`, `levels` y `citation` (vocabulario de
     13-code §7.4) no se construyen — ningún id los consume. Mismo criterio que
     `existential`/`m_of_n` en sufficiency.
3. **La gramática y el checker son shared kernel** (`app/shared/domain/value_domain.py`), no
   dominio de un módulo: `validate_spec` (¿la declaración está bien formada?) y `check_value`
   (¿el valor la cumple?). Evaluation Design importa el primero al mintear; Content Profiling
   el segundo al perfilar. Una sola gramática, imposible de driftear.
4. **La verificación vive en `ContentProfile.ok()`** — el chokepoint por el que pasa todo
   adapter — como **invariante 5** del agregado, junto a las que ya estaban. Una entrada
   `absent` no se chequea: no tiene valor y la ausencia ya es el hallazgo.
5. **Una violación es `InvalidProfile`**, el mismo trato que las otras invariantes del
   agregado (capacidades fuera del namespace, entradas faltantes): un desacuerdo
   adapter ↔ namespace es un error de contrato a arreglar, no un dato a registrar. Un profile
   con forma equivocada no se persiste.
6. **Las filas sin value domain se borran** (migración `0008`), no se backfillean: el
   namespace se re-crea con `import-instrument`, que es donde los value domains se autorean.
   Admisible por la misma razón que 13-code §2 dio para las tablas de rúbrica/evaluación —
   son datos de fase experimental y ningún study pinneó todavía una versión de instrumento.
   Retira de paso el `practice_exercises` huérfano de un borrador anterior.

## Relación con ADR-0014

**No lo supersede: lo completa.** ADR-0014 decide **dónde nacen los ids y quién tiene
autoridad semántica** (la demanda), y eso queda intacto — incluidos el lint de definiciones,
los alias, el diccionario como vista generable y los extras no-canónicos. Este ADR agrega
**qué más se declara en ese mismo acto de minteo** y **quién verifica que la oferta lo
cumpla**. Los triggers de reversión de ADR-0014 (recrear el registry con gobernanza) siguen
vigentes tal cual; si alguno se dispara, el `value_domain` viaja con el id.

## Consecuencias

- (+) El desacuerdo de forma entre demanda y oferta se detecta en el borde de extracción, no
  meses después dentro de un ejecutor — y nunca como un `fail` citado sobre un defecto
  inexistente.
- (+) La declaración de un `data_requirement` pasa a ser el contrato completo (significado +
  forma), que es lo que un autor de adapter necesita para implementar una capacidad sin
  preguntar.
- (+) El costo real fue bajo: la columna, el DTO y el parseo del import ya existían.
- (−) **En el camino automático la violación es silenciosa.** El dispatcher captura toda
  excepción de policy y solo loguea (ADR-0003: el evento queda durable y la policy se puede
  reprocesar), así que un perfilado on-register que viola la forma no deja fila ni evento.
  Se detecta en el camino manual (`profile-content`, `reprofile`, que reportan el error por
  contenido) y en el test de fixtures. No se construye alerting: la decisión es asumirlo
  mientras el volumen sea el de una fase de calibración.
- (−) Los profiles ya persistidos no se re-verifican: el repositorio los reconstruye con el
  constructor, no con `ok()`. Deliberado — un profile almacenado es un hecho pasado, no se
  invalida retroactivamente; regenerarlos es `seed-demo --reset` o una versión nueva de
  adapter.
- (−) La forma declarada es tan buena como la disciplina de quien la escribe. Se mitiga con
  el test que corre cada entrada extraída de los paquetes congelados contra el value domain
  del instrumento que el equipo autorea: cambiar uno sin el otro falla ahí.
- (−) `nullable` estricto (presente y null, no ausente) es más exigente que la intuición
  JSON y va a sorprender a algún autor de adapter. Es el precio de que la omisión nunca sea
  una forma de decir "no había nada".

## Alternativas consideradas

- **Dejar `value_domain` opcional, verificando solo si está declarado** → rechazada: alcanza
  con olvidarse de declararlo para volver exactamente al estado que este ADR corrige, y el
  olvido no deja rastro. La obligatoriedad es lo que convierte la forma en contrato.
- **Checker duplicado en cada módulo** (Conformist puro: la spec cruza como dato y cada lado
  la interpreta con su propia gramática) → rechazada: el dispatch por nombre de tipo
  existiría dos veces, y dos gramáticas que deben coincidir sin nada que las ate es el mismo
  problema de drift que ADR-0014 resolvió para los ids. El shared kernel es acoplamiento
  deliberado a **una gramática de formato**, no al dominio del otro módulo.
- **Registrar la violación como profile `failed`** en vez de `InvalidProfile` → rechazada:
  un profile `failed` dice "el paquete no se pudo leer", que es una condición del evaluando;
  un desacuerdo de forma es un bug de código. Registrarlo como dato lo normaliza. (El
  argumento en contra —que corta un batch— no aplica: `reprofile` ya captura `InvalidProfile`
  por contenido y sigue.)
- **Adoptar JSON Schema** → rechazada: resuelve un problema mucho más grande que el que hay
  (composición, refs, condicionales) y su superficie invita a expresar restricciones
  semánticas que pertenecen a la `pass_condition` del criterion, no a la forma del dato
  (ADR-0010). Seis ids no justifican una dependencia ni su curva. El camino de vuelta es
  barato si un día hace falta: la gramática de acá es un subconjunto expresable en él.
- **Validar la forma dentro de cada ejecutor de assessor** → rechazada: mueve el chequeo
  aguas abajo del punto donde el dato se persiste como evidencia, lo duplica una vez por
  ejecutor y deja el profile mal formado en la base igual.

## Referencias

ADR-0009 (sin cita no es evidencia — la garantía que esto protege) · ADR-0014 (el ADR que
este completa) · ADR-0010 (los umbrales normativos viven en la `pass_condition`, no en la
forma) · ADR-0016 y ADR-0019 (el assessor se debe al instrumento, no al formato — de dónde
sale el riesgo) · 12-define §Content Profiling (invariantes 1–4 del agregado) · 13-code §7.4
(la spec mínima que este ADR realiza y acota) · `docs/seed/instruments/learnpack-course-qa-v1.yaml`
(los seis value domains, derivados de lo que el adapter `LearnpackV1` realmente produce).
