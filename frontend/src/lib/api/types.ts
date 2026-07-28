/**
 * TypeScript mirror of the FastAPI contract (each module's infrastructure/router.py).
 * Field names match the JSON exactly (snake_case).
 */

export type Uuid = string;
export type MetadataValueType = "string" | "string_list";

export interface Me {
  assessor_id: Uuid;
  role: string; // "admin" | "evaluator"
  email: string | null;
  display_name: string | null;
}

export interface MetadataEntry {
  key: string;
  value: string | string[];
  value_type: MetadataValueType;
}

export interface ContentResponse {
  content_id: Uuid;
  generating_system: string;
  external_id: string;
  version: string;
  consumable_url: string;
  metadata: MetadataEntry[];
}

export interface AssessorResponse {
  assessor_id: Uuid;
  role: string;
  email: string | null;
  display_name: string | null;
}

export interface AssignmentResponse {
  assignment_id: Uuid;
  campaign_id: Uuid;
  content_id: Uuid;
  assessor_id: Uuid;
  status: string; // assigned | opened | submitted | cancelled
  rubric_version_id: string;
}

export interface Criterion {
  criterion_id: string;
  order: number;
  dimension: string;
  prompt: string;
  guidance: string;
  anchor_low: string;
  anchor_high: string;
}

export interface AssignmentDetail {
  assignment_id: Uuid;
  status: string;
  content_id: Uuid;
  consumable_url: string;
  metadata: MetadataEntry[];
  rubric_version_id: string;
  scale_min: number;
  scale_max: number;
  criteria: Criterion[];
}

export interface ScoreInput {
  criterion_id: string;
  score: number;
  comment: string | null;
}

export interface SubmitEvaluationRequest {
  assignment_id: Uuid;
  scores: ScoreInput[];
}

export interface EvaluationResponse {
  evaluation_id: Uuid;
  assessor_id: Uuid;
  content_id: Uuid;
  rubric_version_id: string;
  scores: ScoreInput[];
}

export interface CampaignResponse {
  campaign_id: Uuid;
  rubric_version_id: string;
  required_evaluations_per_content: number;
  content_ids: Uuid[];
  metadata_view: string[];
  status: string; // draft | open | closed
}

export interface ContentProgress {
  content_id: Uuid;
  submitted_count: number;
  required: number;
  completed: boolean;
}

export interface CampaignProgress {
  campaign_id: Uuid;
  rubric_version_id: string;
  status: string;
  required_evaluations_per_content: number;
  coverage: number;
  contents: ContentProgress[];
}

export interface GoldenStatus {
  campaign_id: Uuid;
  rubric_version_id: string;
  coverage: number;
  threshold: number;
  usable: boolean;
  established_at: string | null;
}

// --- Reporting -------------------------------------------------------------

export interface Dispersion {
  stdev: number | null;
  mean_pairwise_abs_diff: number | null;
  exact_agreement_pct: number | null;
  rater_count: number;
}

export interface CriterionSummary {
  criterion_id: string;
  average: number;
  dispersion: Dispersion;
}

export interface IndividualEvaluation {
  evaluation_id: Uuid;
  assessor_id: Uuid;
  assessor_name: string | null;
  submitted_at: string | null;
  superseded: boolean;
  scores: ScoreInput[];
}

export interface ContentScores {
  content_id: Uuid;
  external_id: string;
  generating_system: string;
  version: string;
  average: number | null;
  evaluator_count: number;
  criteria: CriterionSummary[];
  evaluations: IndividualEvaluation[];
}

export interface AssessorAverage {
  assessor_id: Uuid;
  display_name: string | null;
  email: string | null;
  evaluation_count: number;
  average: number | null;
}

export interface ScoresReport {
  contents: ContentScores[];
  assessors: AssessorAverage[];
  global_average: number | null;
}

export interface AssignmentCounts {
  assigned: number;
  opened: number;
  submitted: number;
  cancelled: number;
  pending: number;
}

export interface AssessorProgress {
  assessor_id: Uuid;
  display_name: string | null;
  counts: AssignmentCounts;
}

export interface ContentProgressRow {
  content_id: Uuid;
  external_id: string;
  counts: AssignmentCounts;
}

export interface ProgressReport {
  by_assessor: AssessorProgress[];
  by_content: ContentProgressRow[];
}

// --- Requests --------------------------------------------------------------

export interface RegisterContentRequest {
  generating_system: string;
  external_id: string;
  consumable_url: string;
  version?: string;
  metadata: Record<string, unknown>;
}

export interface OpenCampaignRequest {
  rubric_version_id: string;
  required_evaluations_per_content: number;
  content_ids: Uuid[];
  metadata_view: string[];
  golden_coverage_threshold?: number;
}

export interface AssignContentRequest {
  content_id: Uuid;
  assessor_id: Uuid;
}
