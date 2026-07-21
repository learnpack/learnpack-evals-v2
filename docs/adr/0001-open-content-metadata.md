# ADR-0001 — Content metadata abierta y validada por schema

**Estado:** aceptada · **Fecha:** 2026-07 · **Contexto DDD:** Content Registry / Orchestration

## Contexto
La metadata de un contenido varía **por tipo de contenido** (un curso LearnPack, un futuro
video, un artículo… no comparten campos) y **por campaña de evaluación** (qué metadata se le
presenta o exige al evaluador depende de la tarea). El caso `lessonPlan` —que se agregó y luego
se descartó al cambiar el alcance de lo que ve el evaluador— mostró que hardcodear campos fijos
en el dominio es frágil y lo contamina con detalles que cambian.

## Decisión
1. **Metadata intrínseca del contenido = colección abierta y tipada.**
   `ContentMetadata` = set de `MetadataEntry {key, value, valueType}`. **Sin** struct de campos
   fijos. El dominio nunca referencia keys concretas (`objectives`, `audience`, …).
2. **Validación por `MetadataSchema` (reference data).** Un `MetadataSchema` ligado al
   `GeneratingSystem`/tipo declara keys permitidas/requeridas y tipos. Es config/dato, no código.
3. **Vista/requisitos por campaña.** `EvaluationCampaign.metadataView` define qué keys se
   presentan/requieren al evaluador. La variabilidad "por campaña" vive acá, no en el contenido.
4. **Ingesta vía ACL.** Un ACL en el borde de Content Registry traduce los campos crudos del
   sistema externo (LearnPack) a `MetadataEntry`.
5. **Presentación en adapters/UI.** Cómo se renderiza (iframe/link, orden, labels) no es dominio.

## Consecuencias
- (+) Dominio limpio y extensible: nuevos tipos de contenido o campañas requieren **config, no
  código**. Nada de `if metadata.X`.
- (+) Separa lo intrínseco (contenido) de lo extrínseco (campaña).
- (+) Evita el churn tipo `lessonPlan`.
- (−) Un poco más de indirección que campos fijos; hace falta validación por schema.
- **MVP:** se siembra **un** schema `learnpack-v1 = {learningObjectives, targetAudience,
  prerequisites}`; la campaña v1 presenta todo. La abstracción es abierta pero el instance es uno.

## Alternativas consideradas
- **Struct de campos fijos** (`objectives`, `audience`, `lessonPlan`…) → rechazada: contamina y
  es rígida (lo demostró `lessonPlan`).
- **Bag totalmente libre sin schema** → rechazada: pierde significado y validación (anémico).
- **Subclases polimórficas por tipo de contenido** → más pesada; colección abierta + schema
  cubre el caso con menos ceremonia.
