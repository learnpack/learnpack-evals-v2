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

/** The identity of an automated assessor: the artifact, and the lineage it owes itself to. */
export interface AutomatedIdentity {
  name: string;
  version: string;
  instrument_id: string;
}

export interface AssessorResponse {
  assessor_id: Uuid;
  role: string;
  email: string | null;
  display_name: string | null;
  /** The Source axis: the two kinds are structurally different (ADR-0016). */
  kind: "human" | "automated";
  /** Present exactly when `kind === "automated"`. */
  automated: AutomatedIdentity | null;
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

export type StudyStatus = "declared" | "prepared" | "open" | "signed_off";

export interface StudyResponse {
  study_id: Uuid;
  name: string;
  /** Optional and never defaulted from the name: an absent description is absent. */
  description: string | null;
  status: StudyStatus;
  instrument_version_id: string | null;
  /** The judge whose verdicts are this study's result (ADR-0042). Pinned once, before
   *  opening, like the instrument. Null on studies declared before the pin existed — those
   *  read every author, which is what they always did. The id only: the label is joined
   *  from the assessor-package list, which is keyed by it. */
  assessor_id: Uuid | null;
  brief_ids: Uuid[];
  /** Which generator versions the round measures (ADR-0044): `"all"`, or exactly these.
   *  `null` while a draft has not declared it — which is what `open` refuses. */
  generator_scope: GeneratorScope | null;
  content_ids: Uuid[];
  created_at: string | null;
  opened_at: string | null;
  signed_off_at: string | null;
}

/** The three states a claim can be in, named once. The report's per-content claims, the
 *  dry run's, and the generator-level distribution are one vocabulary — extracted so a
 *  palette can be `Record<ClaimStatus, …>` and a fourth state cannot be forgotten. */
export type ClaimStatus = "supported" | "refuted" | "insufficient";

export interface StudyReportClaim {
  claimId: string;
  status: ClaimStatus;
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

/** Who produced a judgment (ADR-0042). `name`/`version` identify an automated artifact and
 *  are null for a human assessor, whose identity is a credential — so `assessorId` is the
 *  one field that is always there, and `assessorLabel` is what renders either. */
export interface AssessorRef {
  assessorId: string;
  name: string | null;
  version: string | null;
}

export interface StudyReportContent {
  contentId: string;
  externalId: string;
  packageFormat: string;
  briefId: string | null;
  generatorVersionId: string | null;
  judgmentId: string | null;
  /** Null when the course carries no judgment; absent on reports frozen at schemaVersion 1. */
  assessor?: AssessorRef | null;
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
  /** Absent on reports frozen before ADR-0037 — those are frozen; render as empty. */
  executionErrors?: { perContent: { contentId: string; count: number }[]; note: string };
  /** Absent on reports frozen at schemaVersion 1 (before ADR-0042), for the same reason. */
  mixedAssessors?: { assessors: AssessorRef[]; note: string };
}

export interface StudyReport {
  schemaVersion: number;
  studyId: string;
  name: string;
  description: string | null;
  instrumentVersionId: string;
  signedOffAt: string;
  signedOffBy: string | null;
  dataset: { size: number; briefIds: string[]; contentIds: string[] };
  judgmentIdsUsed: Record<string, string>;
  /** The distinct authors of the judgments this document reflects. Absent at schemaVersion 1. */
  assessorsUsed?: AssessorRef[];
  contents: StudyReportContent[];
  generatorLevel: StudyReportGenerator[];
  caveats: StudyReportCaveats;
}

export interface StudyReportResponse {
  study_id: Uuid;
  report: StudyReport;
  signed_off_at: string;
}

/** Demand × supply for one (instrument version, package format): which criteria have a
 *  datum to read in that format and which do not. The form uses it to say, before anything
 *  is saved, how much of the instrument a course in that format can actually answer —
 *  marked, never hidden, because readiness informs and does not block. */
export interface MatchingResponse {
  instrumentVersionId: string;
  packageFormat: string;
  adapterVersion: string | null;
  /** Null when no adapter is registered for the format at all. */
  extractionAccepted: boolean | null;
  criteria: {
    criterionId: string;
    requiredData: string[];
    missingData: string[];
    covered: boolean;
    onMissingEvidence: string;
  }[];
  unmetDemand: { dataRequirementId: string; criterionIds: string[] }[];
  claims: { claimId: string; criteria: number; coveredCriteria: number }[];
}

/** A gap a composed-on-read document names instead of refusing to answer: the study is not
 *  finished being set up, and saying so beats a 404 (the readiness stance). */
export interface StudyGap {
  gap: string;
}

export interface FrozenRecord {
  exists: boolean;
  note: string;
}

/** What signing off WOULD write, composed on read. The same document as `StudyReport`
 *  minus `signedOffAt` — removed rather than nulled, because a null renders as the epoch —
 *  plus what it says about itself. With no instrument pinned, `contents` and
 *  `generatorLevel` come back empty and `gaps` says why. */
export interface StudyReportPreview
  extends Omit<StudyReport, "signedOffAt" | "instrumentVersionId"> {
  instrumentVersionId: string | null;
  documentKind: "preview";
  composedAt: string;
  frozenRecord: FrozenRecord;
  gaps: StudyGap[];
}

/** The body every layer of the report renders: exactly what the two payloads have in common.
 *
 *  Both are assignable to it — `StudyReport` structurally, the preview by construction — so
 *  neither needs an adapter. And `signedOffAt` is not merely absent here, it is UNREADABLE,
 *  which turns the unguarded `new Date(report.signedOffAt)` this rewrite replaces into a
 *  compile error rather than a screen that says "Signed off" about a study nobody signed. */
export type ReportBody = Omit<StudyReport, "signedOffAt" | "instrumentVersionId"> & {
  instrumentVersionId: string | null;
};

/** The difference between the two documents, isolated in a union exactly one component reads.
 *
 *  `recomposed` is a preview of a study that already HAS a frozen record: the same content,
 *  a different claim about itself, and the band must not say the same thing about both. */
export type DocumentSource =
  | { kind: "frozen"; signedOffAt: string; signedOffBy: string | null }
  | { kind: "preview"; composedAt: string; gaps: StudyGap[] }
  | { kind: "recomposed"; composedAt: string; gaps: StudyGap[]; note: string };

// --- the per-criterion record across a study's dataset -----------------------------------
// Composed on read like fitness, and for its reason: it must not travel inside the report's
// frozen jsonb. It is the only place the quote grounding a PASS is readable, and the only
// one with a denominator per criterion.

export interface CriterionOutcomeCell {
  contentId: string;
  outcome: CriterionOutcomeState;
  /** True when the state was derived mechanically; false when an executor judged it. */
  derived: boolean;
  quote: string | null;
  locator: Record<string, unknown> | null;
  failureMode: string | null;
  comment: string | null;
  executionCause: ExecutionCause | null;
}

/** The same six states as `CriterionOutcomeState`, in the camelCase spelling the domain
 *  counts them with (`evidence_basis` uses it too). Two spellings of one vocabulary is not
 *  ideal, but they are two different things — one names a state, one names a tally — and
 *  inventing a third would not fix it. */
export type OutcomeTally =
  | "pass"
  | "fail"
  | "noEvidence"
  | "notApplicable"
  | "notAssessed"
  | "executionError";

export interface CriterionOutcomeSection {
  criterionId: string;
  claimIds: string[];
  distribution: Record<OutcomeTally, number>;
  /** `observed` of `of`: the denominator is the DATASET, so a criterion nothing judged
   *  reads `0 of 20` rather than going missing. */
  coverage: { observed: number; of: number };
  outcomes: CriterionOutcomeCell[];
}

export interface CriterionOutcomeContent {
  contentId: string;
  externalId: string;
  briefId: string | null;
  generatorVersionId: string | null;
  judgmentId: string | null;
  derivedAt: string | null;
}

export interface CriterionOutcomes {
  studyId: string;
  status: StudyStatus;
  instrumentVersionId: string | null;
  computedAt: string;
  signal: "evidence";
  /** Which judgment each course is read through. A signed-off study answers through the
   *  ones its frozen report recorded, so re-evaluating afterwards cannot make the evidence
   *  disagree with the document it explains. */
  judgmentBasis: { basis: "current" | "signedOffReport"; note: string };
  /** And whose those judgments are: a cell's quote is what SOME judge read, and more than
   *  one entry means two cells of one criterion are not the same measurement. */
  assessorsUsed: AssessorRef[];
  gaps: StudyGap[];
  contents: CriterionOutcomeContent[];
  criteria: CriterionOutcomeSection[];
  contentsWithoutJudgment: string[];
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
  executionError: number;
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

// --- Evaluating a study in batch (ADR-0040) ---------------------------------
// Started and not awaited: `POST` hands back a run id and the run is read while it
// advances, because an evaluation of twenty courses takes minutes.

/** `cancelled` is a person stopping it; `failed` is the run stopping itself over a cause
 *  that would repeat for every course; `refused` is the runner itself breaking. */
export type BatchRunStatus = "running" | "done" | "cancelled" | "failed" | "refused";
export type BatchCourseStatus = "evaluated" | "skipped" | "failed" | "cancelled";

export interface BatchCourse {
  content_id: Uuid;
  external_id: string;
  /** The fitness's grouping axis (ADR-0039): repeats of one commission read together. */
  brief_id: Uuid | null;
  status: BatchCourseStatus;
  /** Filled exactly when something went wrong. */
  cause: string | null;
  duration_ms: number;
  llm_calls: number;
  evaluation_id: Uuid | null;
}

export interface BatchRun {
  run_id: Uuid;
  study_id: Uuid;
  instrument_version_id: string;
  assessor: string;
  status: BatchRunStatus;
  started_at: string;
  finished_at: string | null;
  elapsed_ms: number;
  total: number;
  done: number;
  evaluated: number;
  failed: number;
  skipped: number;
  /** `[typical, slowest]` in ms, from the courses this run has already timed — null until
   *  it has timed one, because a promise from no measurements is a guess. */
  remaining_ms_estimate: [number, number] | null;
  current_activity: string | null;
  error: string | null;
  courses: BatchCourse[];
}

export interface StudyEvaluations {
  study_id: Uuid;
  instrument_version_id: string | null;
  courses: number;
  /** Read from the database, not from a run: it survives a restart and counts a batch
   *  someone ran from the CLI. */
  evaluated: number;
  /** The same count split by who produced it. `evaluated` answers how much of the study has
   *  been judged at all; this answers how much a given assessor would skip — the question
   *  the start dialog is actually asking, and the one an instrument-wide number cannot. */
  evaluated_by_assessor: AssessorProgress[];
  default_concurrency: number;
  runs: BatchRun[];
}

export interface AssessorProgress {
  assessor_id: Uuid;
  name: string | null;
  version: string | null;
  evaluated: number;
}

export interface StartBatchRequest {
  /** Omitted now that the study pins its assessor (ADR-0042 §10). Sending one is still
   *  accepted and is checked against the pin — a disagreement is refused, not resolved. */
  assessor_name?: string;
  assessor_version?: string;
  re_evaluate?: boolean;
  concurrency?: number;
}

export interface BatchRunStarted {
  run_id: Uuid;
}

/** A commission the study was computed over (ADR-0039): the id joins, the hash identifies
 *  it in any store, and the text is what a person recognises. Never a score — the brief
 *  groups the projection and nothing is pooled per brief. */
export interface FitnessBrief {
  briefId: string;
  briefHash: string | null;
  brief: string | null;
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
  briefs: FitnessBrief[];
  assessorCoverage: {
    /** Who MAY judge with this instrument version — ratification, not participation. */
    ratifiedAssessors?: string[];
    /** Who DID judge this study. More than one and these values pool more than one judge. */
    assessorsUsed?: AssessorRef[];
    notAssessed?: number;
    executionErrors?: number;
    note?: string;
  };
  contents: (FitnessLevel & {
    contentId: string;
    externalId: string;
    briefId: string | null;
    generatorVersionId: string | null;
    judged: boolean;
  })[];
  generators: (FitnessLevel & {
    generatorVersionId: string;
    name: string | null;
    version: string | null;
    contents: number;
    /** What THIS version's values were not computed over (ADR-0044). Two versions whose
     *  coverage differs are each correct and their difference is not — the equal-coverage
     *  rule of ADR-0023 §7, at the grain a study comparing versions is read. Optional and
     *  read defensively: a payload composed before this key existed has none. */
    coverage?: { notAssessed: number; executionErrors: number };
  })[];
  unknownExclusions?: string[];
  study: Partial<FitnessLevel>;
}

// --- Requests --------------------------------------------------------------

/** The recipe's second axis, in the one shape that cannot contradict itself (ADR-0044 §1):
 *  every version the briefs bring, said out loud, or exactly the ones named. */
export type GeneratorScope = "all" | Uuid[];

/** A study can be created empty or complete: none of the selection is binding until the
 *  study opens, which is what pins it (ADR-0043 §1). */
export interface DeclareStudyRequest {
  name: string;
  description?: string | null;
  instrument_version_id?: string | null;
  assessor_id?: Uuid | null;
  brief_ids?: Uuid[];
  generator_scope?: GeneratorScope;
}

/** A partial update of a draft, where absent and null mean different things: omitting a key
 *  leaves it alone, sending `assessor_id: null` CLEARS the judge — which is what re-pointing
 *  a draft at a norm that judge never ratified requires. */
export interface UpdateStudyDraftRequest {
  name?: string;
  description?: string | null;
  instrument_version_id?: string;
  assessor_id?: Uuid | null;
  brief_ids?: Uuid[];
  generator_scope?: GeneratorScope;
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

// --- Local source intake (`/dev/local-courses`, ADR-0035) --------------------
// Only exists under AUTH_MODE=local, and admin-only on top: outside local mode every path
// answers 404, which is why nothing here is reachable from a deployed console.

/** One filesystem tree the backend may register from. `courses/` is always the first. */
export interface SourceRootResponse {
  key: string;
  path: string;
  /** Prefix of every locator registered from this root. */
  url_base: string;
  /** Live: the directory is there now. It does NOT say the tree is served — only a scan's
   *  mount probe knows that (a root created after boot is not mounted until a restart). */
  exists: boolean;
  builtin: boolean;
}

export interface FolderEntry {
  name: string;
  /** Root-relative, which is what `scan` and `register` take. */
  path: string;
  /** How many folders it holds — how "you are one level too high" becomes visible. */
  child_dir_count: number;
}

export interface BrowseResponse {
  root: string;
  path: string;
  /** Null at the root itself; "" one level below it. */
  parent: string | null;
  entries: FolderEntry[];
}

/** What registering a folder WOULD do, derived from the rules registration applies:
 *  `new_version` is a known course whose bytes are new and whose declared version is free —
 *  it registers, so calling it `new` would misread a regenerated population. */
export type ScanVerdict = "new" | "new_version" | "unchanged" | "conflict" | "unreadable";

export interface ExistingContent {
  content_id: Uuid;
  version: string;
  generator_version_id: Uuid | null;
  /** False for rows registered by hand before ADR-0027 — they never dedupe by content. */
  has_hash: boolean;
}

export interface ScanCandidate {
  name: string;
  path: string;
  verdict: ScanVerdict;
  external_id: string | null;
  title: string | null;
  artifact_count: number | null;
  content_hash: string | null;
  /** Why discovery refused, for `unreadable` only. */
  error: string | null;
  /** The registered row this verdict is about. For `new_version`, the most recent one. */
  existing: ExistingContent | null;
  /** The existing row declares no generator, so the attribution act applies (ADR-0024). */
  can_attribute_generator: boolean;
}

export interface ScanRequest {
  root: string;
  path: string;
  package_format: string;
  version: string;
}

export interface ScanResponse {
  /** False when the locators these folders would register are not actually fetchable —
   *  registering refuses too, so this is a reason to stop, not a warning to dismiss. */
  mount_ok: boolean;
  mount_detail: string | null;
  candidates: ScanCandidate[];
}

/** One folder per request, deliberately: each created course auto-profiles inside it. */
export interface RegisterLocalRequest {
  root: string;
  path: string;
  package_format: string;
  version: string;
  /** Required, null declares `unknown` (ADR-0024). */
  generator_version_id: Uuid | null;
  edit_provenance?: EditProvenance;
}

export interface RegisterLocalResponse {
  content: ContentResponse;
  /** False when the package was already registered unchanged — a no-op, not an error. */
  created: boolean;
  artifact_count: number;
  /** True when the registered content still declares no generator — including the no-op
   *  case, where the generator this request declared was discarded (ADR-0035 §9). */
  can_attribute_generator: boolean;
}

// --- Calibration (the dry-run over HTTP) ------------------------------------

/** One quality of the pedagogical vocabulary, with the dimension it groups under. */
export interface QualityReferenceResponse {
  quality_id: string;
  dimension_id: string | null;
}

/** One version of a package's lineage, and whether that package may judge with it.
 *
 * Ratification is per (assessor, instrument version) — ADR-0019 — so this is a matrix,
 * never a flag. A draft is listed and never ratified: its remedy is publishing it. */
export interface LineageVersion {
  instrument_version_id: string;
  status: "draft" | "published" | "deprecated";
  ratified: boolean;
  ratified_at: string | null;
  ratified_by_name: string | null;
}

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
  /** Null until the first ratification mints the identity row (ADR-0019 §2). */
  assessor_id: Uuid | null;
  lineage_versions: LineageVersion[];
}

export interface RatifyAssessorRequest {
  name: string;
  version: string;
  instrument_version_id: string;
  /** One id per executed criterion whose normative text changed (ADR-0019 §3). */
  confirmed: string[];
}

export interface RatifyAssessorResponse {
  assessor_id: Uuid;
  instrument_version_id: string;
  newly_ratified: boolean;
  newly_registered: boolean;
}

/** The 409 body when executed criteria changed: what has to be decided, one by one. */
export interface RatificationDelta {
  criterion_id: string;
  change: "new" | "changed";
  pass_condition: string;
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
  | "not_assessed"
  | "execution_error";

export interface ExecutionCause {
  /** The assessor's failed unit of work; criteria fed by one task share one cause. */
  task: string | null;
  kind: string;
  message: string;
}

export interface PreviewOutcome {
  criterion_id: string;
  outcome: CriterionOutcomeState;
  /** True when the state was derived mechanically; false when an executor judged it. */
  derived: boolean;
  quote: string | null;
  locator: Record<string, unknown> | null;
  failure_mode: string | null;
  /** Present exactly on execution_error: why THIS run could not judge it (ADR-0037). */
  execution_cause: ExecutionCause | null;
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

// A dry run is started, not awaited: with LLM criteria it takes minutes, so the request
// hands back an id and the run is read while it advances.

export interface PreviewRunStarted {
  run_id: Uuid;
}

export interface PreviewRunStep {
  /** `criterion` — an executor landed a verdict; `llm_call` — one attempt at a model. */
  kind: "criterion" | "llm_call";
  label: string;
  detail: string;
  /** False only when something malfunctioned: a `fail` is a verdict, not a malfunction. */
  ok: boolean;
  duration_ms: number;
  /** Milliseconds from the start of the run — measured on the server. */
  at_ms: number;
}

/** Named, not merely described: each kind maps to the remedy that fixes it. */
export type PreviewRunErrorKind =
  | "profile_missing"
  | "instrument_missing"
  | "assessor_failed"
  | "unexpected";

export interface PreviewRunError {
  kind: PreviewRunErrorKind;
  message: string;
}

export interface PreviewRun {
  run_id: Uuid;
  status: "running" | "done" | "failed";
  started_at: string;
  finished_at: string | null;
  elapsed_ms: number;
  steps: PreviewRunStep[];
  result: PreviewEvaluationResponse | null;
  error: PreviewRunError | null;
}

/** One ATTEMPT at one LLM call, whole: a task that needed three rounds to satisfy its
 *  output contract left three of these, and the second one's `messages` end with the
 *  validator's complaint about the first. */
export interface LlmCallRecord {
  task_id: string | null;
  attempt: number;
  model_requested: string;
  model_answered: string | null;
  /** Which upstream served it: OpenRouter routes one model id to several. */
  provider: string | null;
  /**
   * What was asked for besides the conversation — temperature, output budget, response
   * format, whether the model may reason. It decides the answer as much as the prompt
   * does: `drafts-hybrid:1` failed every run on this half, not on its prompts.
   */
  sampling: Record<string, unknown>;
  messages: { role: string; content: string }[];
  response_text: string | null;
  /** `length` means the answer was cut off — it surfaces as "not valid JSON". */
  finish_reason: string | null;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  error: string | null;
}

export interface PreviewRunTrace {
  run_id: Uuid;
  status: string;
  /** Where the same records were written, when the backend has LLM_TRACE_DIR set. */
  trace_path: string | null;
  calls: LlmCallRecord[];
}
