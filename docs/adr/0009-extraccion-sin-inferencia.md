# ADR-0009 — El motor no infiere: solo evidencia declarada y citada

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** extracción de contenido /
Pedagogical Evaluation

## Contexto

Para evaluar un criterion hace falta el dato que ese criterion mide: para juzgar los objetivos con
Revised Bloom, hacen falta los objetivos. Pero no todo contenido educativo los declara, y aun
declarándolos, no siempre en un campo de metadata.

Ante eso aparece la tentación de que un LLM **infiera** lo que falta ("este curso parece enseñar
X, así que su objetivo sería entender X") y evaluar sobre esa reconstrucción. Hay que decidir si
se permite.

## Decisión

**El motor evalúa únicamente lo que el contenido dice. No completa lo que no dice.**

1. **Toda evidencia extraída se cita.** Cada elemento del `ContentProfile` lleva su
   `EvidenceProvenance` con un **locator**: la cita verbatim y dónde está en el contenido. Sin
   cita, no es evidencia.
2. **Valores de provenance:** `declared_structured` (está en un campo de metadata) ·
   `declared_in_content` (está enunciado textualmente en el cuerpo, con cita) · `absent`.
   **No existe `inferred`.**
3. **No se registra `confidence`.** Si la regla es "solo lo que está escrito", lo que hace falta
   es la cita, no un número de confianza — que sería la muleta para justificar la reconstrucción.
4. **La ausencia es un resultado, no un dato faltante.** "Este curso no enuncia objetivos" es un
   hallazgo pedagógico de primera clase y se reporta como tal.
5. **Enlazar elementos ya declarados sigue siendo extracción**, no inferencia: vincular un ítem de
   evaluación con un objetivo es lícito cuando **ambos extremos existen y se citan**. Lo prohibido
   es producir un extremo que no está.
6. **Decidir si un enunciado vago cuenta como objetivo es juicio, no extracción.** "Aprenderás
   sobre bucles" se extrae tal cual; que sea vago es un hallazgo de la evaluación, no un fallo del
   extractor.

## Consecuencias

- (+) **No se lava un defecto real.** La alineación constructiva de Biggs —uno de los frameworks
  fundantes— empieza por objetivos explícitos. Un curso sin ellos tiene un problema; inferirlos lo
  convertiría en un aprobado y destruiría precisamente el hallazgo más valioso.
- (+) **Auditabilidad.** Todo score se puede rastrear hasta una cita del contenido. Un
  `QualityJudgment` deja de depender de la buena fe del extractor.
- (+) **Los extractores se vuelven testeables con fixtures**, incluso los que usen LLM: su salida
  es una cita verificable, no un juicio.
- (+) **Reproducibilidad.** Una extracción citable es estable entre corridas, lo que sostiene la
  comparabilidad que la calibración necesita.
- (−) Habrá contenidos que produzcan profiles muy pobres y, por lo tanto, evaluaciones con mucha
  ausencia. **Es el resultado correcto**, pero exige que el reporte comunique cobertura junto al
  score (ver ADR-0011) para que "no evaluado" no se lea como "malo".
- (−) Cierra la puerta a evaluar contenido de calidad estructural muy baja con la misma rúbrica
  que uno bien documentado. Se acepta: son casos distintos y deben verse distintos.

## Fuera del motor, permitido

Sugerirle **al autor** que declare objetivos —"este curso no los enuncia; por lo que se ve parece
enseñar X, considerá declararlo"— es una función de producto legítima, claramente etiquetada como
sugerencia. **Nunca entra como insumo de una evaluación ni de un score.**

## Alternativas consideradas

- **Permitir inferencia marcada como tal, con `confidence`**, y dejar que el consumidor decida →
  rechazada: en la práctica el score se consume sin leer la provenance, y la marca no evita que un
  defecto real se convierta en un número aprobatorio. Además contradice el punto 4.
- **Inferir solo cuando el criterion lo autorice** → rechazada: mueve la decisión a cada criterion
  y garantiza que alguien la active por conveniencia; el problema epistémico no cambia según quién
  lo permita.
- **Rechazar el contenido que no declare lo necesario** → rechazada: convierte en error lo que es
  información valiosa sobre el contenido.

## Referencias

Ninguna práctica madura de evaluación puntúa evidencia reconstruida: `k12-teacher-skills` puntúa
"what pass requires" sobre lo presente; Quality Matters juzga Met/Not Met sobre evidencia
presente; los protocolos de observación docente puntúan **solo lo observado**. Detalle en
`notes/discover-proceso-bloom-sin-objetivos.md` y `notes/research-motor-evaluacion-multiangulo.md`.
</content>
