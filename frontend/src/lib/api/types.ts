/**
 * TypeScript mirror of the FastAPI contract (each module's infrastructure/router.py).
 * Field names match the JSON exactly (snake_case).
 */

export type Uuid = string;

export interface Me {
  assessor_id: Uuid;
  role: string; // "admin" | "evaluator"
  email: string | null;
  display_name: string | null;
}

export type EditProvenance = "pure" | "human_edited" | "unknown";

export interface ContentResponse {
  content_id: Uuid;
  package_format: string;
  external_id: string;
  version: string;
  /** Null when no deployed, human-consumable instance is declared (ADR-0028). */
  consumable_url: string | null;
  brief_id: Uuid | null;
  generator_version_id: Uuid | null;
  edit_provenance: EditProvenance;
  /** Set only when the generator was attributed after registration (ADR-0024). */
  generator_attributed_by?: Uuid | null;
  generator_attributed_at?: string | null;
}

export interface AttributeGeneratorRequest {
  generator_version_id: Uuid;
}

export interface PackageArtifact {
  kind: string;
  locator: string;
  format: string | null;
}

export interface ContentPackageResponse {
  content_id: Uuid;
  package_format: string;
  consumable_url: string | null;
  artifacts: PackageArtifact[];
}

/** The lineage (ADR-0031): what a study means by "this generator". Owns its versions. */
export interface GeneratorResponse {
  generator_id: Uuid;
  name: string;
}

export interface GeneratorVersionResponse {
  generator_version_id: Uuid;
  generator_id: Uuid;
  /** Joined from the lineage — a version is identified as "<name> <version>" everywhere. */
  name: string;
  version: string;
  metadata: Record<string, unknown>;
}

export interface RegisterGeneratorRequest {
  name: string;
  /** Echo of the name a near-miss refusal named, declaring this is a different generator. */
  confirm_distinct_from?: string;
}

export interface RegisterGeneratorVersionRequest {
  version: string;
  metadata?: Record<string, unknown>;
}

export interface BriefResponse {
  brief_id: Uuid;
  brief: string;
  fields: Record<string, unknown>;
}

export interface RegisterBriefRequest {
  brief: string;
  fields?: Record<string, unknown>;
}

export interface InstrumentClaim {
  claim_id: string;
  statement: string;
  quality_ids: string[];
  warrants: string[];
  alternative_explanations: string[];
  sufficiency_rule: string;
}

export interface InstrumentCriterion {
  criterion_id: string;
  statement: string | null;
  pass_condition: string;
  failure_modes: string[];
  claim_ids: string[];
  required_data: string[];
  on_missing_evidence: string;
  eligible_sources: string[];
  condition: Record<string, unknown> | null;
}

export interface InstrumentBinding {
  package_format: string;
  task_variables: Record<string, unknown>;
}

export interface InstrumentResponse {
  instrument_version_id: string;
  instrument_id: string;
  version: string;
  name: string;
  purpose: string;
  status: "draft" | "published" | "deprecated";
  claims: InstrumentClaim[];
  criteria: InstrumentCriterion[];
  bindings: InstrumentBinding[];
}

export interface ProfileEntryResponse {
  data_requirement_id: string;
  provenance: "declared_structured" | "declared_in_content" | "absent";
  value: unknown;
  quote: string | null;
  locator: Record<string, unknown> | null;
}

export interface ProfileExtraResponse {
  name: string;
  value: unknown;
  quote: string | null;
  locator: Record<string, unknown> | null;
}

export interface ProfileResponse {
  profile_id: Uuid;
  content_id: Uuid;
  external_id: string | null;
  content_version: string | null;
  package_format: string;
  adapter_version: string;
  status: "ok" | "failed";
  error: string | null;
  profiled_at: string | null;
  entries: ProfileEntryResponse[];
  extras: ProfileExtraResponse[];
}

export interface ProfileCapabilitiesResponse {
  package_format: string;
  adapter_version: string;
  capabilities: string[];
  accepted: boolean;
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
  instrument_version_id: string;
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
  consumable_url: string | null;
  instrument_version_id: string;
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
  instrument_version_id: string;
  scores: ScoreInput[];
}

export interface CampaignResponse {
  campaign_id: Uuid;
  instrument_version_id: string;
  required_evaluations_per_content: number;
  content_ids: Uuid[];
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
  instrument_version_id: string;
  status: string;
  required_evaluations_per_content: number;
  coverage: number;
  contents: ContentProgress[];
}

export interface GoldenStatus {
  campaign_id: Uuid;
  instrument_version_id: string;
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
  package_format: string;
  version: string;
  evaluator_count: number;
  criteria: CriterionSummary[];
  evaluations: IndividualEvaluation[];
}

/** Per-criterion profile per content — never a score across criteria (ADR-0011). */
export interface ScoresReport {
  contents: ContentScores[];
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

// --- Evaluation studies (13-code §3.6/§6) ----------------------------------

export type StudyStatus = "declared" | "prepared" | "open" | "published";

export interface StudyResponse {
  study_id: Uuid;
  purpose: string;
  status: StudyStatus;
  instrument_version_id: string | null;
  brief_ids: Uuid[];
  content_ids: Uuid[];
  created_at: string | null;
  opened_at: string | null;
  published_at: string | null;
}

export interface StudyReportClaim {
  claimId: string;
  status: "supported" | "refuted" | "insufficient";
  evidenceBasis: Record<string, number>;
  insufficiencyCause?: string;
}

export interface StudyReportFinding {
  findingId: string;
  claimId: string;
  criterionId: string;
  failureMode: string;
  quote: string | null;
  quoteAbsentCause?: string; // ADR-0021: present when the quote is null
  locator: unknown;
}

export interface StudyReportContent {
  contentId: string;
  externalId: string;
  packageFormat: string;
  briefId: string | null;
  generatorVersionId: string | null;
  judgmentId: string | null;
  derivedAt?: string;
  coverage?: unknown;
  claims?: StudyReportClaim[];
  findings?: StudyReportFinding[];
}

export interface StudyReportGeneratorClaim {
  claimId: string;
  statement: string;
  distribution: Record<string, number>;
  excludedNotApplicable: number;
  notEvaluated: number;
  coverage: { evaluated: number; of: number };
}

export interface StudyReportGenerator {
  generatorVersionId: string;
  name: string | null;
  version: string | null;
  contentsCounted: number;
  perClaim: StudyReportGeneratorClaim[];
}

export interface StudyReportCaveats {
  insufficientEvidence: { contentId: string; claimId: string; cause: string }[];
  unresolvedDisagreements: unknown[];
  unknownExclusions: { contentIds: string[]; note: string };
  unacceptedAdapters: { packageFormat: string; adapterVersion: string | null }[];
  briefCompleteness: { briefId: string; promptRecorded: boolean; origin: string | null }[];
  contentsWithoutJudgment: string[];
  taskVariablePatterns: { status: string; reason: string };
}

export interface StudyReport {
  schemaVersion: number;
  studyId: string;
  purpose: string;
  instrumentVersionId: string;
  publishedAt: string;
  publishedBy: string | null;
  dataset: { size: number; briefIds: string[]; contentIds: string[] };
  judgmentIdsUsed: Record<string, string>;
  contents: StudyReportContent[];
  generatorLevel: StudyReportGenerator[];
  caveats: StudyReportCaveats;
}

export interface StudyReportResponse {
  study_id: Uuid;
  report: StudyReport;
  published_at: string;
}

export interface StudyReadinessGap {
  gap: string;
  criterionId?: string;
  packageFormat?: string;
  missingData?: string[];
  instrumentVersionId?: string;
}

export interface StudyReadiness {
  studyId: string;
  status: StudyStatus;
  informative: boolean;
  studyGaps: StudyReadinessGap[];
  formats: {
    packageFormat: string;
    adapterVersion: string | null;
    extractionAccepted: boolean | null;
  }[];
  claims: { claimId: string; gaps: StudyReadinessGap[] }[];
}

// --- Fitness projection (ADR-0023) ------------------------------------------
// An optimization signal, never a judgment: it lives on its own endpoint and is shown
// apart from the report, which by ADR-0011 publishes no aggregate score.

export interface FitnessCoverage {
  criteria: number;
  denominator: number;
  pass: number;
  fail: number;
  noEvidence: number;
  notApplicable: number;
  notAssessed: number;
}

export interface FitnessQuality {
  /** null means UNDEFINED — nothing was measurable. It is never rendered as a zero. */
  fitness: number | null;
  dimensionId: string | null;
  coverage: FitnessCoverage;
}

export interface FitnessDimension {
  fitness: number | null;
  coverage: { qualities: number; defined: number };
}

export interface FitnessLevel {
  qualities: Record<string, FitnessQuality>;
  dimensions: Record<string, FitnessDimension>;
}

export interface StudyFitness {
  studyId: string;
  status: StudyStatus;
  instrumentVersionId: string | null;
  formulaVersion: string;
  computedAt: string;
  signal: "optimization";
  denominatorRule: {
    numerator: string[];
    penalizing: string[];
    excluded: string[];
    note: string;
  };
  gaps: { gap: string }[];
  assessorCoverage: {
    ratifiedAssessors?: string[];
    notAssessed?: number;
    note?: string;
  };
  contents: (FitnessLevel & {
    contentId: string;
    externalId: string;
    generatorVersionId: string | null;
    judged: boolean;
  })[];
  generators: (FitnessLevel & {
    generatorVersionId: string;
    name: string | null;
    version: string | null;
    contents: number;
  })[];
  unknownExclusions?: string[];
  study: Partial<FitnessLevel>;
}

// --- Requests --------------------------------------------------------------

export interface DeclareStudyRequest {
  purpose: string;
}

export interface PinStudyInstrumentRequest {
  instrument_version_id: string;
}

export interface ComposeStudyDatasetRequest {
  brief_ids: Uuid[];
}

/** Registration by mechanical discovery (ADR-0027): identity, artifacts and content hash
 * come from the package itself; the form declares only source + generator + provenance. */
export interface RegisterBySourceRequest {
  package_format: string;
  /** http(s) base URL of the package — local directories are the CLI's business. */
  source_locator: string;
  /** Required, null declares `unknown` (ADR-0024): silence is not a declaration. */
  generator_version_id: Uuid | null;
  edit_provenance?: EditProvenance;
  version?: string;
}

export interface RegisterBySourceResponse {
  content: ContentResponse;
  /** False when the same content (by hash) was already registered — a no-op, not an error. */
  created: boolean;
  artifact_count: number;
}

export interface OpenCampaignRequest {
  instrument_version_id: string;
  required_evaluations_per_content: number;
  content_ids: Uuid[];
  golden_coverage_threshold?: number;
}

export interface AssignContentRequest {
  content_id: Uuid;
  assessor_id: Uuid;
}

/** `GET /dev/identities` — only exists under AUTH_MODE=local (ADR-0008). */
export interface DevIdentity {
  email: string;
  display_name: string | null;
  role: string; // "admin" | "evaluator"
}

// --- Calibration (the dry-run over HTTP) ------------------------------------

/** One automated assessor package from the in-code registry (ADR-0016). */
export interface AssessorPackageResponse {
  name: string;
  version: string;
  display_name: string;
  /** The instrument lineage the artifact owes itself to (ADR-0019). */
  instrument_id: string;
  executes: string[];
  /** criterion_id → the declared reason for abstaining (ADR-0018). */
  abstains: Record<string, string>;
  /** True when the package carries LLM tasks: real calls, needs the backend's LLM_API_KEY. */
  uses_llm: boolean;
}

export interface PreviewEvaluationRequest {
  content_id: Uuid;
  instrument_version_id: string;
  assessor_name: string;
  assessor_version: string;
}

export type CriterionOutcomeState =
  | "pass"
  | "fail"
  | "no_evidence"
  | "not_applicable"
  | "not_assessed";

export interface PreviewOutcome {
  criterion_id: string;
  outcome: CriterionOutcomeState;
  /** True when the state was derived mechanically; false when an executor judged it. */
  derived: boolean;
  quote: string | null;
  locator: Record<string, unknown> | null;
  failure_mode: string | null;
}

export interface PreviewClaim {
  claim_id: string;
  status: "supported" | "refuted" | "insufficient";
  /** The domain's own camelCase vocabulary: pass, fail, noEvidence, … */
  evidence_basis: Record<string, number>;
}

export interface PreviewFinding {
  claim_id: string;
  criterion_id: string;
  failure_mode: string;
  quote: string | null;
  locator: Record<string, unknown> | null;
}

export interface PreviewMetric {
  metric_id: string;
  value: unknown;
}

export interface PreviewEvaluationResponse {
  instrument_version_id: string;
  instrument_status: string;
  assessor: { name: string; version: string; display_name: string };
  outcomes: PreviewOutcome[];
  claims: PreviewClaim[];
  findings: PreviewFinding[];
  coverage: Record<string, unknown>;
  metrics: PreviewMetric[];
  /** Always false — the contract states what the page claims (dry run). */
  persisted: false;
}
