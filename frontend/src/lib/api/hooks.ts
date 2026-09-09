"use client";

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { useAuthHeaders } from "@/lib/auth";
import { ApiError, apiFetch, type RequestOptions } from "./client";
import type {
  AcceptExtractionResponse,
  AssessorPackageResponse,
  AssessorResponse,
  AssignContentRequest,
  AttributeGeneratorRequest,
  AssignmentDetail,
  AssignmentResponse,
  BatchRun,
  BatchRunStarted,
  BriefResponse,
  BrowseResponse,
  CampaignProgress,
  CampaignReport,
  CampaignResponse,
  ClaimValidityReport,
  DatasetResponse,

  ContentResponse,
  CourseSession,
  CriterionOutcomes,
  DeclareConsumableUrlRequest,
  DeclareDatasetRequest,
  DeclareStudyRequest,
  EvaluationResponse,
  GeneratorResponse,
  GeneratorVersionResponse,
  GoldenStatus,
  InstrumentResponse,
  InvitationResponse,
  InviteAssessorRequest,
  Me,
  MintDatasetVersionRequest,
  OpenCampaignRequest,
  UpdateStudyDraftRequest,
  PreviewEvaluationRequest,
  PreviewRun,
  PreviewRunStarted,
  PreviewRunTrace,
  ProfileCapabilitiesResponse,
  ProfileResponse,
  ProgressReport,
  QualityReferenceResponse,
  RatifyAssessorRequest,
  RatifyAssessorResponse,
  ReferenceInstrumentResponse,
  RenameCampaignRequest,
  RenameDatasetRequest,
  RubricDetailResponse,
  RegisterBriefRequest,
  RegisterBySourceRequest,
  RegisterBySourceResponse,
  RegisterGeneratorRequest,
  RegisterGeneratorVersionRequest,
  RegisterLocalRequest,
  RegisterLocalResponse,
  ScanRequest,
  ScanResponse,
  SourceRootResponse,
  StartBatchRequest,
  MatchingResponse,
  StudyEvaluations,
  StudyFitness,
  StudyReadiness,
  StudyReportPreview,
  StudyReportResponse,
  StudyResponse,
  SubmitEvaluationRequest,
  Uuid,
} from "./types";

/** A fetcher that injects the current identity headers on every call (see `lib/auth`). */
export function useApi() {
  const getAuthHeaders = useAuthHeaders();
  return useCallback(
    async <T>(path: string, options: Omit<RequestOptions, "headers"> = {}): Promise<T> => {
      return apiFetch<T>(path, { ...options, headers: await getAuthHeaders() });
    },
    [getAuthHeaders],
  );
}

export const queryKeys = {
  me: ["me"] as const,
  myAssignments: ["me", "assignments"] as const,
  assignment: (id: Uuid) => ["assignments", id] as const,
  courseSession: (id: Uuid) => ["assignments", id, "course-session"] as const,
  contents: ["admin", "contents"] as const,
  packageFormats: ["admin", "contents", "formats"] as const,
  generators: ["admin", "generators"] as const,
  generatorVersions: ["admin", "generator-versions"] as const,
  briefs: ["admin", "briefs"] as const,
  instruments: ["admin", "instruments"] as const,
  profiles: ["admin", "profiles"] as const,
  profilingCapabilities: ["admin", "profiling", "capabilities"] as const,
  datasets: ["admin", "datasets"] as const,
  dataset: (id: Uuid) => ["admin", "datasets", id] as const,
  campaigns: ["admin", "campaigns"] as const,
  referenceInstruments: ["admin", "reference", "instruments"] as const,
  referenceInstrument: (id: string) => ["admin", "reference", "instruments", id] as const,
  campaignAssignments: (id: Uuid) => ["admin", "campaigns", id, "assignments"] as const,
  campaignProgress: (id: Uuid) => ["admin", "campaigns", id, "progress"] as const,
  golden: (id: Uuid) => ["admin", "campaigns", id, "golden"] as const,
  // All three coordinates are in the key: each of them changes the answer, and a key that
  // omitted one would serve another pair's numbers from the cache (ADR-0063 §7).
  claimValidity: (campaign: Uuid, assessor: Uuid, instrument: string) =>
    ["admin", "validity", campaign, assessor, instrument] as const,
  campaignReport: (id: Uuid) => ["admin", "campaigns", id, "report"] as const,
  assessors: ["admin", "assessors"] as const,
  invitations: ["admin", "invitations"] as const,
  assessorPackages: ["admin", "assessor-packages"] as const,
  previewRun: (id: Uuid | string) => ["admin", "evaluations", "preview", id] as const,
  previewRunTrace: (id: Uuid | string) =>
    ["admin", "evaluations", "preview", id, "trace"] as const,
  qualityReference: ["admin", "reference", "qualities"] as const,
  progress: ["admin", "progress"] as const,
  studies: ["admin", "studies"] as const,
  study: (id: Uuid) => ["admin", "studies", id] as const,
  studyReport: (id: Uuid) => ["admin", "studies", id, "report"] as const,
  // A SIBLING of `studyReport`, not a child: nested under it, the preview would be
  // invalidated by the non-exact `studyReport` line in `invalidateStudy` without ever being
  // named there — and a key nobody names is a key nobody maintains.
  studyReportPreview: (id: Uuid) => ["admin", "studies", id, "report-preview"] as const,
  studyCriterionOutcomes: (id: Uuid) =>
    ["admin", "studies", id, "criterion-outcomes"] as const,
  studyReadiness: (id: Uuid) => ["admin", "studies", id, "readiness"] as const,
  studyFitness: (id: Uuid) => ["admin", "studies", id, "fitness"] as const,
  matching: (versionId: string, packageFormat: string) =>
    ["admin", "instruments", versionId, "matching", packageFormat] as const,
  studyEvaluations: (id: Uuid) => ["admin", "studies", id, "evaluations"] as const,
  studyEvaluationRun: (id: Uuid, runId: Uuid | string) =>
    ["admin", "studies", id, "evaluations", runId] as const,
  localSourceRoots: ["dev", "local-courses", "roots"] as const,
  localSourceFolder: (root: string, path: string) =>
    ["dev", "local-courses", "browse", root, path] as const,
};

// --------------------------------------------------------------------- identity

export function useMe(options?: Partial<UseQueryOptions<Me>>) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api<Me>("/me"),
    staleTime: 5 * 60_000,
    ...options,
  });
}

// -------------------------------------------------------------------- evaluator

export function useMyAssignments() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.myAssignments,
    queryFn: () => api<AssignmentResponse[]>("/me/assignments"),
  });
}

export function useAssignment(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.assignment(id),
    queryFn: () => api<AssignmentDetail>(`/assignments/${id}`),
  });
}

/**
 * The course URL with its session in it (ADR-0061).
 *
 * Its own request rather than a field on the assignment: a session is minted and
 * short-lived, and the assignment detail is a description any refetch may serve from cache.
 *
 * `retry: false` because a failure here is not a blip — minting reaches two external
 * services, and retrying would provision again while the evaluator waits. `staleTime` keeps
 * a re-render from asking for a second session; the page holds the URL only as long as the
 * evaluator is on it.
 */
export function useCourseSession(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.courseSession(id),
    queryFn: () => api<CourseSession>(`/assignments/${id}/course-session`),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useOpenAssignment() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: Uuid) =>
      api<AssignmentResponse>(`/assignments/${id}/open`, { method: "POST" }),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: queryKeys.assignment(id) });
      qc.invalidateQueries({ queryKey: queryKeys.myAssignments });
    },
  });
}

export function useSubmitEvaluation() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitEvaluationRequest) =>
      api<EvaluationResponse>("/evaluations", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.myAssignments }),
  });
}

// ------------------------------------------------------------------------ admin

export function useContents() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.contents,
    queryFn: () => api<ContentResponse[]>("/admin/contents"),
  });
}

/** The package formats discovery supports — what the form offers (ADR-0027). */
export function usePackageFormats() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.packageFormats,
    queryFn: () => api<string[]>("/admin/contents/formats"),
  });
}

/** Register by mechanically discovering a package source (ADR-0027). */
export function useRegisterBySource() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterBySourceRequest) =>
      api<RegisterBySourceResponse>("/admin/contents/register-by-source", {
        method: "POST",
        body,
      }),
    onSuccess: () => invalidateAfterRegistration(qc),
  });
}

/**
 * Registering a course writes more than the course.
 *
 * The intake ACL derives its commission and mints a brief when that one is new (ADR-0022),
 * and profiling runs inside the same request when the format's extraction is accepted
 * (ADR-0029). Invalidating only the contents leaves both of those stale — the extraction
 * column reads the profile that was just written, and a round is composed out of briefs, so
 * a commission minted a second ago would simply not be on offer.
 */
function invalidateAfterRegistration(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: queryKeys.contents });
  qc.invalidateQueries({ queryKey: queryKeys.briefs });
  qc.invalidateQueries({ queryKey: queryKeys.profiles });
}

// ------------------------------------- local source intake (dev only, ADR-0035)
// These four exist only under AUTH_MODE=local; outside it every path answers 404, so the
// page that uses them never renders in a deployed console.

export function useLocalSourceRoots(enabled: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.localSourceRoots,
    queryFn: () => api<SourceRootResponse[]>("/dev/local-courses/roots"),
    enabled,
  });
}

export function useLocalSourceFolder(root: string, path: string, enabled: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.localSourceFolder(root, path),
    queryFn: () =>
      api<BrowseResponse>(
        `/dev/local-courses/browse?root=${encodeURIComponent(root)}&path=${encodeURIComponent(path)}`,
      ),
    enabled,
  });
}

/** The preview: reads and hashes every artifact of every folder, so it is slow and never
 *  retried — a second identical pass would cost the same and answer the same. */
export function useScanLocalSource() {
  const api = useApi();
  return useMutation({
    retry: false,
    mutationFn: (body: ScanRequest) =>
      api<ScanResponse>("/dev/local-courses/scan", { method: "POST", body }),
  });
}

/** One folder per call — the selection is a loop in the page, which is what gives it a
 *  progress line and bounds each request (ADR-0035 §5). */
export function useRegisterLocalPackage() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (body: RegisterLocalRequest) =>
      api<RegisterLocalResponse>("/dev/local-courses/register", { method: "POST", body }),
    onSuccess: () => invalidateAfterRegistration(qc),
  });
}

/** Records a generator learnt after registration — once, one way (ADR-0024). */
export function useAttributeGenerator() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contentId, body }: { contentId: Uuid; body: AttributeGeneratorRequest }) =>
      api<ContentResponse>(`/admin/contents/${contentId}/generator`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.contents }),
  });
}

/**
 * Points a registered course at its deployment (ADR-0054).
 *
 * Shaped like its neighbour above with one deliberate difference: this act **may be
 * repeated**. A generator link is a discovery — always true, merely learnt late — while a
 * deployment is a statement about the world right now, and a course that moves needs a
 * repair. Invalidating the contents is enough: the assign picker and the campaign form read
 * that same query to decide whether a course can be put in front of a human.
 *
 * On settle rather than on success, unlike its neighbour: the write is conditional on the
 * value that was read (ADR-0054 §4), so a refusal is itself evidence that the row on screen
 * is stale — refetching is the repair, not noise.
 */
export function useDeclareConsumableUrl() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contentId, body }: { contentId: Uuid; body: DeclareConsumableUrlRequest }) =>
      api<ContentResponse>(`/admin/contents/${contentId}/consumable-url`, { method: "POST", body }),
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.contents }),
  });
}

/** The lineages. `/generators` and `/generator-versions` are two resources since ADR-0031:
 *  the first is what a name identifies, the second is what a content declares. */
export function useGenerators() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.generators,
    queryFn: () => api<GeneratorResponse[]>("/admin/generators"),
  });
}

export function useGeneratorVersions() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.generatorVersions,
    queryFn: () => api<GeneratorVersionResponse[]>("/admin/generator-versions"),
  });
}

export function useCreateGenerator() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterGeneratorRequest) =>
      api<GeneratorResponse>("/admin/generators", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.generators }),
  });
}

export function useCreateGeneratorVersion() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ generatorId, body }: { generatorId: Uuid; body: RegisterGeneratorVersionRequest }) =>
      api<GeneratorVersionResponse>(`/admin/generators/${generatorId}/versions`, {
        method: "POST",
        body,
      }),
    // A new version changes what the version list shows, not the lineage list — but the
    // grouped view reads both, so both are invalidated.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.generators });
      qc.invalidateQueries({ queryKey: queryKeys.generatorVersions });
    },
  });
}

export function useInstruments() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.instruments,
    queryFn: () => api<InstrumentResponse[]>("/admin/instruments"),
  });
}

export function usePublishInstrument() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    // Not a Uuid: instrument version ids look like "learnpack-course-qa-v1".
    mutationFn: (instrumentVersionId: string) =>
      api<InstrumentResponse>(`/admin/instruments/${instrumentVersionId}/publish`, {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.instruments }),
  });
}

export function useProfiles() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.profiles,
    queryFn: () => api<ProfileResponse[]>("/admin/profiles"),
  });
}

export function useProfilingCapabilities() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.profilingCapabilities,
    queryFn: () => api<ProfileCapabilitiesResponse[]>("/admin/profiling/capabilities"),
  });
}

/**
 * The two acts of the profiling workbench (ADR-0012).
 *
 * Both change what the capabilities band and the profile list say, so both invalidate the
 * pair. Reading is one request per content on purpose — a batch is a loop in the caller
 * (ADR-0035 §5), which is what keeps a slow package visible and a failure bounded.
 */
export function useAcceptExtraction() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (packageFormat: string) =>
      api<AcceptExtractionResponse>(
        `/admin/profiling/${encodeURIComponent(packageFormat)}/accept`,
        { method: "POST" },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.profilingCapabilities });
      qc.invalidateQueries({ queryKey: queryKeys.profiles });
    },
  });
}

export function useProfileContent() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (contentId: Uuid) =>
      api<ProfileResponse>(`/admin/contents/${contentId}/profile`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.profiles }),
  });
}

export function useBriefs() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.briefs,
    queryFn: () => api<BriefResponse[]>("/admin/briefs"),
  });
}

export function useCreateBrief() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterBriefRequest) =>
      api<BriefResponse>("/admin/briefs", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.briefs }),
  });
}

/** The reference instrument versions a campaign may pin — published only (ADR-0056). */
export function useReferenceInstruments() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.referenceInstruments,
    queryFn: () => api<ReferenceInstrumentResponse[]>("/admin/reference/instruments"),
  });
}

/** One reference instrument with every item — the rubric page reads its content from here. */
export function useReferenceInstrument(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.referenceInstrument(id),
    queryFn: () => api<RubricDetailResponse>(`/admin/reference/instruments/${id}`),
  });
}

// ---- datasets (ADR-0058) ----------------------------------------------------

/** Every write moves both reads: the list carries each dataset's whole version line. */
function invalidateDatasets(qc: ReturnType<typeof useQueryClient>, id: Uuid) {
  qc.invalidateQueries({ queryKey: queryKeys.datasets, exact: true });
  qc.invalidateQueries({ queryKey: queryKeys.dataset(id) });
}

export function useDatasets() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.datasets,
    queryFn: () => api<DatasetResponse[]>("/admin/datasets"),
  });
}

export function useDataset(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.dataset(id),
    queryFn: () => api<DatasetResponse>(`/admin/datasets/${id}`),
  });
}

export function useDeclareDataset() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DeclareDatasetRequest) =>
      api<DatasetResponse>("/admin/datasets", { method: "POST", body }),
    onSuccess: (created) => {
      invalidateDatasets(qc, created.dataset_id);
      // Seed the detail cache: the list sends the reader straight there.
      qc.setQueryData(queryKeys.dataset(created.dataset_id), created);
    },
  });
}

/** Freezes the next membership. A membership equal to the current one answers 409, which
 *  the caller reports as the fact it is rather than as a failure. */
export function useMintDatasetVersion(id: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MintDatasetVersionRequest) =>
      api<DatasetResponse>(`/admin/datasets/${id}/versions`, { method: "POST", body }),
    onSuccess: () => invalidateDatasets(qc, id),
  });
}

export function useRenameDataset(id: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RenameDatasetRequest) =>
      api<DatasetResponse>(`/admin/datasets/${id}`, { method: "PATCH", body }),
    onSuccess: () => invalidateDatasets(qc, id),
  });
}

export function useCampaigns() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.campaigns,
    queryFn: () => api<CampaignResponse[]>("/admin/campaigns"),
  });
}

export function useCreateCampaign() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OpenCampaignRequest) =>
      api<CampaignResponse>("/admin/campaigns", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns }),
  });
}

export function useRenameCampaign(id: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RenameCampaignRequest) =>
      api<CampaignResponse>(`/admin/campaigns/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns }),
  });
}

export function useCampaignProgress(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.campaignProgress(id),
    queryFn: () => api<CampaignProgress>(`/admin/campaigns/${id}/progress`),
  });
}

export function useCampaignAssignments(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.campaignAssignments(id),
    queryFn: () => api<AssignmentResponse[]>(`/admin/campaigns/${id}/assignments`),
  });
}

/** How much each claim of this assessor version follows that campaign's panel (ADR-0063).
 *
 *  The campaign is the caller's choice and it is optional: with none chosen there is nothing
 *  to ask for, and no badge — which is a different fact from `unvalidated`, where the
 *  comparison was made and did not conclude. */
export function useClaimValidity(
  campaign: Uuid | null,
  assessor: Uuid | null,
  instrument: string | null,
) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.claimValidity(campaign ?? "", assessor ?? "", instrument ?? ""),
    queryFn: () =>
      api<ClaimValidityReport>(
        `/admin/validity?campaign=${encodeURIComponent(campaign!)}` +
          `&assessor=${encodeURIComponent(assessor!)}` +
          `&instrument=${encodeURIComponent(instrument!)}`,
      ),
    enabled: Boolean(campaign && assessor && instrument),
  });
}

export function useGoldenStatus(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.golden(id),
    queryFn: () => api<GoldenStatus>(`/admin/campaigns/${id}/golden`),
  });
}

/** One campaign's result (ADR-0060). The whole round in one payload — items, courses and
 *  every individual answer — because it is one reading of one campaign, and paging it would
 *  invite reading a part of it as the whole. */
export function useCampaignReport(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.campaignReport(id),
    queryFn: () => api<CampaignReport>(`/admin/campaigns/${id}/report`),
  });
}

export function useAssessors() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.assessors,
    queryFn: () => api<AssessorResponse[]>("/admin/assessors"),
  });
}

/** Granting or withdrawing a role (ADR-0050). Admin-only, refused with a 409 in the two
 *  cases nothing inside the product could undo: the last admin, and your own row. */
export function useChangeAssessorRole() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ assessorId, role }: { assessorId: Uuid; role: string }) =>
      api<AssessorResponse>(`/admin/assessors/${assessorId}`, {
        method: "PATCH",
        body: { role },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assessors });
      // The caller's own role is read from `/me` for the nav and the guards; a grant to
      // somebody else cannot change it, but a stale `me` after any roster write is the
      // kind of thing that only shows up as a missing menu entry.
      qc.invalidateQueries({ queryKey: queryKeys.me });
    },
  });
}

/** Correcting the expertise profile an invitation declared (ADR-0049). Not a grant, so it
 *  carries none of the guardrails a role change does — including on your own row. */
export function useSetAssessorExpertise() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ assessorId, expertise }: { assessorId: Uuid; expertise: string | null }) =>
      api<AssessorResponse>(`/admin/assessors/${assessorId}/expertise`, {
        method: "PATCH",
        body: { expertise },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.assessors }),
  });
}

/** Withdrawing somebody from the roster, or bringing them back (ADR-0051). Not a delete:
 *  what they produced is untouched, and what stops is the future. */
export function useSetAssessorActive() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ assessorId, active }: { assessorId: Uuid; active: boolean }) =>
      api<AssessorResponse>(`/admin/assessors/${assessorId}/active`, {
        method: "POST",
        body: { active },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assessors });
      qc.invalidateQueries({ queryKey: queryKeys.me });
    },
  });
}

/** Who the roster is expecting, and what happened to everyone it expected before
 *  (ADR-0049). Every state, newest first: an accepted row is the record of a registration
 *  that worked, and a revoked one of a decision somebody took. */
export function useInvitations() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.invitations,
    queryFn: () => api<InvitationResponse[]>("/admin/invitations"),
  });
}

/** The act that registers a human evaluator. It creates no account — the assessor appears
 *  at that address's first login — so the assessor list is deliberately NOT invalidated
 *  here: nothing about it changed. */
export function useInviteAssessor() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (body: InviteAssessorRequest) =>
      api<InvitationResponse>("/admin/invitations", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.invitations }),
  });
}

/** Re-send (a fresh window) and revoke. Both act on one pending invitation and refuse with
 *  a 409 once it is no longer pending, which is a fact to report, not a retry. */
function useInvitationAct(act: "resend" | "revoke") {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (invitationId: Uuid) =>
      api<InvitationResponse>(`/admin/invitations/${invitationId}/${act}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.invitations }),
  });
}

export const useResendInvitation = () => useInvitationAct("resend");
export const useRevokeInvitation = () => useInvitationAct("revoke");

/** The in-code registry of automated assessor packages (ADR-0016), as data — with what
 *  each of them has ratified, which is what makes it evaluable at all (ADR-0019). */
export function useAssessorPackages() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.assessorPackages,
    queryFn: () => api<AssessorPackageResponse[]>("/admin/assessor-packages"),
  });
}

/** The ADR-0019 act at its second gate (ADR-0036): irreversible, and never retried.
 *
 * A 409 is not a failure to retry blindly — it carries the criteria whose decision the act
 * is waiting for, and the caller resubmits with them confirmed. */
export function useRatifyAssessor() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ name, version, ...body }: RatifyAssessorRequest) =>
      api<RatifyAssessorResponse>(`/admin/assessor-packages/${name}/${version}/ratify`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.assessorPackages });
      qc.invalidateQueries({ queryKey: queryKeys.assessors });
    },
  });
}

/** The pedagogical vocabulary's quality → dimension grouping (live reference data). */
export function useQualityReference() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.qualityReference,
    queryFn: () => api<QualityReferenceResponse[]>("/admin/reference/qualities"),
  });
}

/** Starts the dry-run and hands back its id: accepts drafts, needs no ratification,
 *  persists nothing. Never retried — an LLM-carrying assessor spends real calls per
 *  attempt, and a second start would be a second bill, not a recovery. */
export function useStartPreviewRun() {
  const api = useApi();
  return useMutation({
    retry: false,
    mutationFn: (body: PreviewEvaluationRequest) =>
      api<PreviewRunStarted>("/admin/evaluations/preview", { method: "POST", body }),
  });
}

/** What each package format in a dataset can answer of the chosen instrument.
 *
 *  One query per format, because the endpoint answers per format and a dataset rarely has
 *  more than two. It runs before a study exists, which is the whole point: the form has to
 *  be able to say what a course in `LearnpackV1` will leave unassessed while the reader can
 *  still change their mind about including it.
 */
export function useMatchings(instrumentVersionId: string | null, formats: string[]) {
  const api = useApi();
  return useQueries({
    queries: formats.map((packageFormat) => ({
      queryKey: queryKeys.matching(instrumentVersionId ?? "", packageFormat),
      queryFn: () =>
        api<MatchingResponse>(
          `/admin/instruments/${instrumentVersionId}/matching?package_format=${encodeURIComponent(packageFormat)}`,
        ),
      enabled: Boolean(instrumentVersionId),
    })),
    combine: (results) => {
      const byFormat = new Map<string, MatchingResponse>();
      for (const result of results) {
        if (result.data) byFormat.set(result.data.packageFormat, result.data);
      }
      return { byFormat, isLoading: results.some((r) => r.isLoading) };
    },
  });
}

/** Starts the batch for a study named at call time rather than at render time — which is
 *  what "Save & evaluate" on a study that did not exist a second ago needs. Never retried,
 *  for `useStartStudyEvaluation`'s reason: a second start is a second bill. */
export function useStartRound() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ studyId, body }: { studyId: Uuid; body: StartBatchRequest }) =>
      api<BatchRunStarted>(`/admin/studies/${studyId}/evaluations`, { method: "POST", body }),
    onSuccess: (_data, { studyId }) => invalidateStudy(qc, studyId),
  });
}

/** The run as it stands, polled while it advances and left alone once it ends.
 *
 * A finished run is not stale data: it is the record of what happened, and refetching it
 * on a window focus would only risk a 404 once the server has forgotten it. */
export function usePreviewRun(runId: Uuid | null) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.previewRun(runId ?? ""),
    queryFn: () => api<PreviewRun>(`/admin/evaluations/preview/${runId}`),
    enabled: runId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    retry: false,
  });
}

/** Every LLM attempt of a run, whole — the prompts as sent and the raw answers.
 *
 * Fetched once the run has ended rather than alongside the polling: these payloads carry
 * entire lesson bodies, and re-pulling them every second to watch a counter grow would
 * cost more than it tells. */
export function usePreviewRunTrace(runId: Uuid | null, ended: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.previewRunTrace(runId ?? ""),
    queryFn: () => api<PreviewRunTrace>(`/admin/evaluations/preview/${runId}/trace`),
    enabled: runId !== null && ended,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    retry: false,
  });
}

// --------------------------------------------------- evaluating a study in batch (ADR-0040)

/** Every read a study's own state feeds, refreshed together — they are one story. The
 *  header count, the readiness, the fitness and the report all restate what the study now
 *  is, and a page that refreshed one and not the others contradicts itself on screen.
 *
 *  Spelled out rather than left to the `["admin", "studies", id]` prefix they share: that
 *  prefix also covers the watched run, and a finished run is not stale data — it is the
 *  record of what happened, and refetching it only risks a 404 once the backend has
 *  forgotten it. Hence `exact` on the keys that have children under them. */
function invalidateStudy(qc: QueryClient, studyId: Uuid): void {
  qc.invalidateQueries({ queryKey: queryKeys.studies, exact: true });
  qc.invalidateQueries({ queryKey: queryKeys.study(studyId), exact: true });
  qc.invalidateQueries({ queryKey: queryKeys.studyEvaluations(studyId), exact: true });
  qc.invalidateQueries({ queryKey: queryKeys.studyReadiness(studyId) });
  qc.invalidateQueries({ queryKey: queryKeys.studyFitness(studyId) });
  qc.invalidateQueries({ queryKey: queryKeys.studyReport(studyId) });
  // Both are composed on read over live judgments, so a batch or an act moves them exactly
  // when it moves everything else here.
  qc.invalidateQueries({ queryKey: queryKeys.studyReportPreview(studyId) });
  qc.invalidateQueries({ queryKey: queryKeys.studyCriterionOutcomes(studyId) });
}

/** How far the study has been evaluated, plus the runs this backend remembers.
 *
 * The count comes from the database, so it is still right after a restart and counts a
 * batch someone ran from the CLI. */
export function useStudyEvaluations(studyId: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studyEvaluations(studyId),
    queryFn: () => api<StudyEvaluations>(`/admin/studies/${studyId}/evaluations`),
    // Polled while this backend is running a batch for the study. Three seconds rather
    // than the run watcher's one: this read joins every judgment of the dataset, and it is
    // the coarse count, not the progress bar.
    refetchInterval: (query) =>
      query.state.data?.runs.some((run) => run.status === "running") ? 3000 : false,
    // A batch started from a terminal is invisible to that interval — the run registry is
    // per-process and the CLI never registers in it — so nothing can watch for one.
    // Coming back to the tab is the moment such a count can be caught up, and it is one
    // cheap read. Deliberately against the client-wide default.
    refetchOnWindowFocus: true,
  });
}

/** Starts the batch and hands back its id. Never retried: every course spends real LLM
 *  calls, so a second start is a second bill, not a recovery. */
export function useStartStudyEvaluation(studyId: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (body: StartBatchRequest) =>
      api<BatchRunStarted>(`/admin/studies/${studyId}/evaluations`, { method: "POST", body }),
    // `exact`: the run keys hang under this one, and there is nothing to refetch about a
    // run that has only just been created.
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.studyEvaluations(studyId), exact: true }),
  });
}

/** The run as it stands, polled while it advances and left alone once it ends — the same
 *  cadence the dry run is watched at.
 *
 *  It also carries the page's only feedback loop. The instant a batch stops is the one
 *  instant everything else on the page is wrong: judgments were persisted while it ran,
 *  and nothing else asks. */
export function useStudyEvaluationRun(studyId: Uuid, runId: Uuid | null) {
  const api = useApi();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.studyEvaluationRun(studyId, runId ?? ""),
    queryFn: () => api<BatchRun>(`/admin/studies/${studyId}/evaluations/${runId}`),
    enabled: runId !== null,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    retry: false,
  });

  // Query-level `onSuccess` is gone in v5, so the terminal transition is watched here. The
  // ref — not the status — is what stops a re-render from paying for it twice: the run is
  // written down the first time it is seen ended, and every later render sees it.
  //
  // It waits for the run's real ending rather than reacting to the cancel act, because
  // cancelling answers while the run is still `running`: courses in flight are still
  // landing, and refreshing then would show a reading that is about to change as final.
  const settled = useRef<Uuid | null>(null);
  const watched = query.data?.run_id ?? null;
  const status = query.data?.status;
  useEffect(() => {
    if (watched === null || status === undefined || status === "running") return;
    if (settled.current === watched) return;
    settled.current = watched;
    invalidateStudy(qc, studyId);
  }, [qc, studyId, watched, status]);

  return query;
}

/** Stop starting new work. What finished stays persisted, so this is safe to click twice —
 *  the endpoint answers with the run rather than an error. */
export function useCancelStudyEvaluation(studyId: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: (runId: Uuid) =>
      api<BatchRun>(`/admin/studies/${studyId}/evaluations/${runId}/cancel`, { method: "POST" }),
    onSuccess: (run) => {
      qc.setQueryData(queryKeys.studyEvaluationRun(studyId, run.run_id), run);
      // `exact`, or the line above is undone: this key is that key's prefix, so a broad
      // invalidation marks the run stale and the refetch it triggers throws away the
      // answer the act just handed us.
      qc.invalidateQueries({ queryKey: queryKeys.studyEvaluations(studyId), exact: true });
    },
  });
}

/** What giving one course to several evaluators came to. Reported as a partial result rather
 *  than as one verdict: a duplicate is somebody else's doing and does not undo the rest. */
export interface AssignOutcome {
  assigned: number;
  /** Whoever the server said was already assigned to that course — a 409, not a failure. */
  duplicates: number;
  /** Anything else that went wrong, one message per evaluator, to show as it came. */
  errors: string[];
}

/**
 * Assign one course to one or more evaluators.
 *
 * The requests go one at a time against the endpoint that already exists, rather than through
 * a bulk act: assigning to three people is not a different act from assigning three times, and
 * the events the campaign records must stay the ones it would have recorded either way. What
 * the loop buys is a single invalidation and a single answer.
 */
export function useAssignContents(campaignId: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      content_id,
      assessor_ids,
    }: {
      content_id: Uuid;
      assessor_ids: Uuid[];
    }): Promise<AssignOutcome> => {
      const outcome: AssignOutcome = { assigned: 0, duplicates: 0, errors: [] };
      for (const assessor_id of assessor_ids) {
        try {
          const body: AssignContentRequest = { content_id, assessor_id };
          await api<AssignmentResponse>(`/admin/campaigns/${campaignId}/assignments`, {
            method: "POST",
            body,
          });
          outcome.assigned += 1;
        } catch (err) {
          const e = err as ApiError;
          if (e.status === 409) outcome.duplicates += 1;
          else outcome.errors.push(e.message);
        }
      }
      return outcome;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.campaignAssignments(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.campaignProgress(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.progress });
    },
  });
}

export function useCancelAssignment(campaignId: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: Uuid) =>
      api<AssignmentResponse>(`/admin/assignments/${assignmentId}/cancel`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.campaignAssignments(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.campaignProgress(campaignId) });
      qc.invalidateQueries({ queryKey: queryKeys.progress });
    },
  });
}

export function useCloseCampaign() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: Uuid) =>
      api<CampaignResponse>(`/admin/campaigns/${id}/close`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.campaigns }),
  });
}

// ---------------------------------------------------- evaluation studies (block 7)

export function useStudies() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studies,
    queryFn: () => api<StudyResponse[]>("/admin/studies"),
  });
}

export function useStudy(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.study(id),
    queryFn: () => api<StudyResponse>(`/admin/studies/${id}`),
  });
}

export function useDeclareStudy() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DeclareStudyRequest) =>
      api<StudyResponse>("/admin/studies", { method: "POST", body }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: queryKeys.studies, exact: true });
      // The caller navigates to the new study at once; seeding it means the detail page
      // renders the study it was asked for instead of a spinner over nothing.
      qc.setQueryData(queryKeys.study(created.study_id), created);
    },
  });
}

function useStudyAct<TBody = void>(path: (id: Uuid) => string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ studyId, body }: { studyId: Uuid; body?: TBody }) =>
      api<StudyResponse>(path(studyId), { method: "POST", body: body ?? undefined }),
    // Choosing changes the instrument the count is taken under and what is counted,
    // opening changes what may run, signing off makes the report exist. One act, one
    // refresh of the whole story.
    onSuccess: (_data, { studyId }) => invalidateStudy(qc, studyId),
  });
}

/** The whole of a draft's setup, in one call. It replaces the three pin/compose acts the
 *  console used to perform, because none of them was binding and a person setting a study
 *  up was never doing three things (ADR-0043 §1). */
export function useUpdateStudyDraft() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ studyId, body }: { studyId: Uuid; body: UpdateStudyDraftRequest }) =>
      api<StudyResponse>(`/admin/studies/${studyId}`, { method: "PATCH", body }),
    onSuccess: (_data, { studyId }) => invalidateStudy(qc, studyId),
  });
}

export function useOpenStudy() {
  return useStudyAct((id) => `/admin/studies/${id}/open`);
}

export function useSignOffStudy() {
  return useStudyAct((id) => `/admin/studies/${id}/sign-off`);
}

export function useStudyReport(id: Uuid, enabled: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studyReport(id),
    queryFn: () => api<StudyReportResponse>(`/admin/studies/${id}/report`),
    enabled,
  });
}

/** What signing off would write, composed on read.
 *
 *  No `enabled` gate, deliberately unlike `useStudyReport` above: this one answers at every
 *  status with its gaps named, and gating it is what made the report invisible until an
 *  irreversible act had already happened. */
export function useStudyReportPreview(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studyReportPreview(id),
    queryFn: () => api<StudyReportPreview>(`/admin/studies/${id}/report/preview`),
  });
}

/** The per-criterion record across the dataset — the only place the quote behind a pass is
 *  readable, and the only one with a denominator per criterion. */
export function useStudyCriterionOutcomes(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studyCriterionOutcomes(id),
    queryFn: () => api<CriterionOutcomes>(`/admin/studies/${id}/criterion-outcomes`),
  });
}

export function useStudyReadiness(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studyReadiness(id),
    queryFn: () => api<StudyReadiness>(`/admin/studies/${id}/readiness`),
  });
}

export function useStudyFitness(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.studyFitness(id),
    queryFn: () => api<StudyFitness>(`/admin/studies/${id}/fitness`),
  });
}

export function useProgressReport() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.progress,
    queryFn: () => api<ProgressReport>("/admin/progress"),
  });
}
