/**
 * One plain sentence per term the console shows to somebody who may not know it (ADR-0069 §2).
 *
 * This is console copy, not a second glossary: each line says what the reader needs in the
 * moment and stops there, and `docs/GLOSSARY.md` stays the full definition. The key is the
 * GLOSSARY's word, the same one the screen shows. A term the console does not name has no
 * entry here.
 */
export const TERMS = {
  assessor:
    "What decides an instrument's criteria for a course. An automated assessor is software, sometimes calling a model; a human one is an evaluator.",
  brief:
    "The request a course was generated from. Courses written from the same brief are what a study compares.",
  campaign:
    "One rating of courses by experts: its own courses, its own evaluators and its own result.",
  claim:
    "One sentence the instrument asserts about one quality of a course. Its criteria are the evidence for it.",
  criterion:
    "One condition that can be checked, with a written pass condition. An assessor decides it for each course, citing the passage it rests on.",
  dataset: "A named set of courses that studies reuse. Changing it makes a new version.",
  dimension: "A group of related qualities. Results are read per dimension, never added up.",
  evaluator: "A person who rates courses in a campaign.",
  "generator version": "One version of the course generator. A study measures one or compares several.",
  instrument:
    "The published list of claims about a course, each with the criteria that check it. It says what is verified; the assessor decides how.",
  profile:
    "What was read out of a course's package, word for word and with where each piece came from. Assessors work from it.",
  quality: "One pedagogical property a course can have, such as how its demand progresses.",
  rubric:
    "What experts answer: one statement per quality, rated 1 to 5. It shares only the qualities with the automated instrument.",
  study:
    "One measurement: a set of courses, one instrument version and one assessor, fixed when it starts so the result can be reproduced.",
} as const;

export type Term = keyof typeof TERMS;
