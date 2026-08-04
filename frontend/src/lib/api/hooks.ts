"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { useCallback } from "react";
import { useAuthHeaders } from "@/lib/auth";
import { apiFetch, type RequestOptions } from "./client";
import type {
  AssessorResponse,
  AssignContentRequest,
  AssignmentDetail,
  AssignmentResponse,
  BriefResponse,
  CampaignProgress,
  CampaignResponse,
  ContentResponse,
  EvaluationResponse,
  GeneratorArtifactResponse,
  GeneratorVersionResponse,
  GoldenStatus,
  InstrumentResponse,
  Me,
  OpenCampaignRequest,
  ProfileCapabilitiesResponse,
  ProfileResponse,
  ProgressReport,
  RegisterBriefRequest,
  RegisterContentRequest,
  RegisterGeneratorArtifactRequest,
  RegisterGeneratorRequest,
  ScoresReport,
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
  contents: ["admin", "contents"] as const,
  generators: ["admin", "generators"] as const,
  generatorArtifacts: (id: Uuid) => ["admin", "generators", id, "artifacts"] as const,
  briefs: ["admin", "briefs"] as const,
  instruments: ["admin", "instruments"] as const,
  profiles: ["admin", "profiles"] as const,
  profilingCapabilities: ["admin", "profiling", "capabilities"] as const,
  campaigns: ["admin", "campaigns"] as const,
  campaignAssignments: (id: Uuid) => ["admin", "campaigns", id, "assignments"] as const,
  campaignProgress: (id: Uuid) => ["admin", "campaigns", id, "progress"] as const,
  golden: (id: Uuid) => ["admin", "campaigns", id, "golden"] as const,
  assessors: ["admin", "assessors"] as const,
  scores: ["admin", "reports", "scores"] as const,
  progress: ["admin", "progress"] as const,
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

export function useCreateContent() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterContentRequest) =>
      api<ContentResponse>("/admin/contents", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.contents }),
  });
}

export function useGenerators() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.generators,
    queryFn: () => api<GeneratorVersionResponse[]>("/admin/generators"),
  });
}

export function useCreateGenerator() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterGeneratorRequest) =>
      api<GeneratorVersionResponse>("/admin/generators", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.generators }),
  });
}

export function useGeneratorArtifacts(generatorId: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.generatorArtifacts(generatorId),
    queryFn: () =>
      api<GeneratorArtifactResponse[]>(`/admin/generators/${generatorId}/artifacts`),
  });
}

export function useCreateGeneratorArtifact(generatorId: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterGeneratorArtifactRequest) =>
      api<GeneratorArtifactResponse>(`/admin/generators/${generatorId}/artifacts`, {
        method: "POST",
        body,
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: queryKeys.generatorArtifacts(generatorId) }),
  });
}

export function useInstruments() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.instruments,
    queryFn: () => api<InstrumentResponse[]>("/admin/instruments"),
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

export function useUpdateContentMetadata() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, metadata }: { id: Uuid; metadata: Record<string, unknown> }) =>
      api<ContentResponse>(`/admin/contents/${id}/metadata`, {
        method: "PATCH",
        body: { metadata },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.contents }),
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

export function useGoldenStatus(id: Uuid) {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.golden(id),
    queryFn: () => api<GoldenStatus>(`/admin/campaigns/${id}/golden`),
  });
}

export function useAssessors() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.assessors,
    queryFn: () => api<AssessorResponse[]>("/admin/assessors"),
  });
}

export function useAssignContent(campaignId: Uuid) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignContentRequest) =>
      api<AssignmentResponse>(`/admin/campaigns/${campaignId}/assignments`, {
        method: "POST",
        body,
      }),
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

export function useScoresReport() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.scores,
    queryFn: () => api<ScoresReport>("/admin/reports/scores"),
  });
}

export function useProgressReport() {
  const api = useApi();
  return useQuery({
    queryKey: queryKeys.progress,
    queryFn: () => api<ProgressReport>("/admin/progress"),
  });
}
