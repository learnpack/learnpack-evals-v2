# ADR-0014 — El vocabulario de datos vive en los evidence models (sin registry propio)

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Rubric/Instrument Authoring ·
Content Profiling

## Contexto

Los criteria requieren datos del contenido ("objetivos", "actividades"); los adapters de
extracción por `GeneratingSystem` los producen. Con N instrumentos y M formatos evolucionando por
separado, ambos lados deben coincidir en qué significa cada dato ("¿'learning objectives' del
criterion se corresponde con 'objectives' del adapter?").

Se consideró resolverlo con un **vocabulario pivote como tercer artefacto** — patrón metadata
registry (ISO/IEC 11179), con mecánica SKOS (prefLabel/altLabel/closeMatch) y el análogo operativo
de los feature stores: términos entrando por ambos lados (rúbricas aportan lo que necesitan,
adapters lo que encuentran), gobernanza bilateral, steward. El coste de mantenimiento de ese
artefacto era una preocupación explícita.

ADR-0013 rompió la simetría que lo justificaba: la cadena *claims → evidencia → observables →
requisitos de datos* le da a la demanda un **origen único con autoridad semántica**. Ya no hay dos
puertas que arbitrar.

## Decisión

**Se descarta el diccionario como artefacto; se conserva su función, incrustada en los evidence
models.**

1. **Ids estables** para los datos que los criteria requieren, minteados **solo del lado de la
   demanda**, en el momento de escribir un evidence rule que necesita uno nuevo. La definición del
   término se escribe como parte del authoring del criterion — trabajo que ADR-0010 ya exige
   (declarar condición de pase y datos requeridos).
2. **El match es por identidad de id, nunca por comparación de strings.** La pregunta "¿este campo
   es aquel concepto?" se contesta una sola vez, por un humano, al escribir el mapeo del adapter.
3. **Unicidad** controlada en la revisión de diseño del instrumento (buscar antes de mintear;
   mismo significado → alias; parecido-pero-distinto → id nuevo con nota del porqué). Verificable
   por lint: ids duplicados con definiciones distintas.
4. **Los adapters declaran capacidades contra esos ids.** El matching conserva sus dos salidas
   estructuradas: **cobertura esperada** (qué porción de un instrumento es evaluable sobre un tipo
   de contenido, antes de evaluar nada) y **demanda insatisfecha** (criteria sin dato).
5. **El "diccionario" es una vista generable** — unión de los ids referenciados por los evidence
   rules vigentes + capacidades declaradas por los adapters — no un artefacto curado.
6. **La oferta sin consumidor se degrada, conscientemente, a domain analysis:** los adapters
   pueden extraer extras bajo **nombres provisionales marcados como no-canónicos**, visibles en el
   visor de perfil, sin gobernanza ni matching. El id canónico se mintea cuando un claim los
   necesite.

## Consecuencias

- (+) El coste de mantenimiento colapsa en trabajo que ya se hace: no hay curaduría separada, ni
  steward, ni proceso de alta bilateral.
- (+) La distinción concepto ≠ representación (el aporte real de ISO 11179) se conserva,
  incrustada donde se escribe la definición.
- (+) Mismo espíritu que ADR-0001 (colección abierta validada por schema: config/dato, no código),
  un nivel más arriba.
- (−) La visibilidad de la riqueza del contenido pasa de estructurada a informal. Aceptado a esta
  escala.
- (−) La puerta única depende de la disciplina de la revisión de diseño; sin ella, el drift
  vuelve.

**Triggers que revierten esta decisión** (recrear el registry como artefacto con gobernanza):

1. Varios diseñadores de instrumentos minteando ids en paralelo sin verse (drift real).
2. Consumidores externos del `ContentProfile` — el vocabulario pasa a ser published language hacia
   afuera y necesita vida propia.
3. Definiciones de observables compartidos divergiendo entre instrumentos.

El camino de vuelta es barato y no destructivo: agregar gobernanza a ids que ya existen (el
movimiento ISO 11179 clásico).

## Alternativas consideradas

- **Registry independiente con mint bilateral** → rechazada por ahora: coste de curaduría sin
  beneficio presente; era necesario solo mientras ningún lado tenía autoridad semántica, y
  ADR-0013 se la dio a la demanda. Triggers de reversión documentados arriba.
- **Matching por strings / ad hoc** → rechazada: el problema de deduplicación ("learning
  objectives" vs "objectives") vuelve intacto, multiplicado por N×M.
- **Adoptar LRMI/schema.org como vocabulario completo** → rechazada (ya analizado): es vocabulario
  de *descubrimiento*, no de *análisis* — no cubre la estructura interna que la evaluación
  necesita. Se toman sus nombres donde calcen, como referencia para zanjar discusiones de naming.

## Referencias

ISO/IEC 11179 (https://en.wikipedia.org/wiki/ISO/IEC_11179) · SKOS
(https://www.w3.org/TR/skos-reference/) · feature stores como análogo
(https://feast.dev/blog/what-is-a-feature-store/) · razonamiento completo en
`notes/genesis-instrumentos-y-ecd.md` y `notes/exploracion-contrato-contentprofile.md`.
</content>
