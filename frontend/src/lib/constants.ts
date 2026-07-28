/** The single published rubric in the MVP (docs/seed/rubric-v1.json, §9). */
export const RUBRIC_VERSION_ID = "learnpack-pedagogical-v1";

export const GENERATING_SYSTEM = "LearnpackV1";

/** LearnpackV1 metadata schema (backend/app/cli.py). Drives the content form + metadata_view. */
export const METADATA_KEYS = [
  { key: "learningObjectives", label: "Learning objectives", type: "string_list", required: true },
  { key: "targetAudience", label: "Target audience", type: "string", required: true },
  { key: "prerequisites", label: "Prerequisites", type: "string_list", required: false },
] as const;
