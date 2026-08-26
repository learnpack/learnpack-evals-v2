/**
 * The single published human instrument in the MVP (`docs/seed/rubric-v2.json`).
 *
 * It is a constant because nothing yet picks one: the console assumes the seed installed
 * exactly this version. That assumption is what makes the id go stale — it did once, when
 * ADR-0052 replaced v1 with v2 and left this line behind, and opening a campaign answered
 * `rubric version must exist and be published` until it was corrected. Whoever seeds a
 * different version corrects it here, or replaces it with the picker the form still lacks.
 */
export const INSTRUMENT_VERSION_ID = "learnpack-pedagogical-v2";
