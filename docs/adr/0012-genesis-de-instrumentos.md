# ADR-0012 — Génesis de instrumentos: el propósito y el contenido originan; los frameworks fundamentan

**Estado:** aceptada · **Fecha:** 2026-08 · **Contexto DDD:** Rubric/Instrument Authoring ·
Pedagogical Evaluation

## Contexto

No estaba definido de dónde nace un instrumento de evaluación. La lectura implícita de la doc de
diseño (frameworks → dimensions → qualities → criteria) sugería un origen teórico: primero el
marco pedagógico, de ahí los criteria. Con el propósito fijado —QA interno: evaluar contenido
generado por IA para mejorar el sistema generador— la pregunta se volvió concreta: cuando aparece
un tipo de contenido nuevo, ¿qué guía el diseño del instrumento?

La exploración mostró dos modos de falla simétricos:

- **Diseño theory-first**: produce instrumentos desanclados del evaluando. La industria no lo
  hace: nadie publica "la rúbrica de Bloom" — EdReports arma sus review tools **por materia y
  nivel**, k12-teacher-skills **por tipo de artefacto**, Quality Matters **por tipo de curso**. En
  teoría de evaluación, la validez no es propiedad del instrumento sino de su **uso para un
  propósito** (Messick).
- **Diseño offer-first** (criteria derivados de lo que el contenido *tiene*): destruye
  `no_evidence` (ADR-0010). Un criterion "¿hay actividades de evaluación?" jamás existiría para un
  generador que nunca las produce — y ese es justamente el hallazgo más valioso.

## Decisión

**Un instrumento es la intersección de tres insumos con roles distintos e irreducibles:**

| Insumo | Fija | Ejemplo |
|---|---|---|
| **Propósito** | el **alcance**: qué superficie se evalúa | UI/UX fuera — el generador no la controla |
| **Tipo de contenido** | el **objeto**: qué elementos existen, dónde viven, qué forma tienen | los instrumentos nacen *para* un tipo |
| **Frameworks** | la **norma**: qué es calidad y qué *debería* estar aunque no esté | sin norma, `no_evidence` es imposible |

1. **Regla de alcance:** se evalúa **la superficie que el generador controla**. Ligada al
   propósito actual (QA interno); si el propósito cambia (p. ej. evaluar contenido de terceros),
   la regla se revisa con él.
2. **Los instrumentos se diseñan *para* un tipo de contenido** (*designed-for*). Reusar un
   instrumento sobre otro tipo es un **acto deliberado** —análogo a revalidar un instrumento
   psicométrico en otra población—, nunca un default. La realización técnica del designed-for es
   el *task model binding* (ADR-0013), no atar la rúbrica entera.
3. **Los frameworks son fundamento (warrant), no origen.** Licencian la inferencia "esto que mido
   es calidad"; `groundedIn` se conserva con ese sentido. Ayudan a identificar qué evaluar y cómo;
   el motivo de existencia del criterion es el contenido a evaluar.
4. **Guarda dura:** la demanda de datos **nunca se deriva de la oferta observada**. La flecha
   normativa (frameworks) debe permanecer independiente del contenido, o un defecto real del
   generador se lava en silencio.

## Consecuencias

- (+) Explica y consolida una decisión ya tomada: el scope de rubric v1 "excluye presentación y
  ecosistema" era esta regla de alcance, aplicada sin nombrarla.
- (+) El diseño de instrumentos **empieza mirando contenido real** (perfiles de contenido
  representativo). El visor de `ContentProfile` es la mesa de trabajo del diseñador — por razones
  de dominio.
- (+) La porción portable de un instrumento queda delimitada: claims y evidence models pueden ser
  agnósticos al tipo; solo el binding se re-liga (ADR-0013).
- (−) Nacen más instrumentos (por tipo de contenido). Mitigado por la porción portable y el patrón
  base + overlay (k12: `shared.csv` + archivo por materia).
- (−) Cada instrumento nuevo exige explicitar su propósito y su designed-for.

## Alternativas consideradas

- **Frameworks como origen** (status quo implícito) → rechazada: sin precedente en la industria,
  y contradice la relatividad de la validez al uso.
- **Criteria derivados de la oferta del contenido** → rechazada: elimina `no_evidence` y con él la
  capacidad de detectar lo que falta.
- **Presets ortogonales al tipo de contenido** (cualquier conjunto de rúbricas aplicable a
  cualquier tipo por defecto) → rechazada: la relación real es *designed-for* + reuso deliberado;
  la ortogonalidad por construcción ocultaría transferencias inválidas de estándares de juicio.

## Referencias

EdReports review tools por materia/nivel (https://edreports.org/process/review-tools) ·
k12-teacher-skills `evals/` (https://github.com/anthropics/k12-teacher-skills) · Messick,
validez relativa al uso · detalle del razonamiento en `notes/genesis-instrumentos-y-ecd.md`.
</content>
