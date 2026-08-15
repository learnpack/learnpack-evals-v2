import type { ProfileCapabilitiesResponse, ProfileResponse, Uuid } from "@/lib/api/types";

/**
 * Whether a course was read, for a screen that is not the profile workbench.
 *
 * The daily loop needs one bit out of profiling — was this course read? — and getting it
 * costs a trip to /admin/profiles today. This derives it from what the console already
 * fetches, so a list of courses can carry it.
 *
 * The rule that governs the whole thing: **the state comes from the profile row, never from
 * whether the format's extraction is accepted.** Automatic profiling declines silently for
 * four different reasons (no adapter for the format · the extraction not accepted · a
 * package the http fetcher cannot reach, ADR-0029 · a profile already recorded), and
 * `profile-content` profiles by hand regardless of acceptance. So a course in a format
 * nobody has accepted may well have been read, and reading `accepted` as a proxy would
 * report it as unread. Acceptance only ever *explains* a missing profile.
 */
export type ExtractionState =
  | { kind: "read" }
  | { kind: "failed"; error: string | null }
  | { kind: "not_read"; reason: NotReadReason };

/** Why no profile exists — as far as the console can tell without asking the backend. */
export type NotReadReason =
  /** No adapter claims this format, so nothing can read it. */
  | "format_unsupported"
  /** An adapter reads it, but nobody has accepted its extraction yet. */
  | "not_accepted"
  /** Readable and accepted, so profiling either never ran or could not reach the package. */
  | "unknown";

/** The current adapter of each format, and whether its extraction is accepted. */
export type CapabilityIndex = Map<string, ProfileCapabilitiesResponse>;

export function indexCapabilities(
  capabilities: ProfileCapabilitiesResponse[] | undefined,
): CapabilityIndex {
  return new Map((capabilities ?? []).map((c) => [c.package_format, c]));
}

/**
 * One profile per content, out of a list that can hold several.
 *
 * A profile is keyed by content AND adapter version, so re-reading a package with a newer
 * adapter leaves the old row in place. The one that answers "was this read" is the one the
 * format's current adapter wrote; failing that, the most recent. Chosen once, here, so the
 * table and the count it sits under can never be reading different rows.
 */
export function indexProfiles(
  profiles: ProfileResponse[] | undefined,
  capabilities: CapabilityIndex,
): Map<Uuid, ProfileResponse> {
  const byContent = new Map<Uuid, ProfileResponse>();
  for (const profile of profiles ?? []) {
    const held = byContent.get(profile.content_id);
    if (!held || supersedes(profile, held, capabilities)) {
      byContent.set(profile.content_id, profile);
    }
  }
  return byContent;
}

function supersedes(
  candidate: ProfileResponse,
  held: ProfileResponse,
  capabilities: CapabilityIndex,
): boolean {
  const current = capabilities.get(candidate.package_format)?.adapter_version;
  if (current) {
    const candidateIsCurrent = candidate.adapter_version === current;
    const heldIsCurrent = held.adapter_version === current;
    if (candidateIsCurrent !== heldIsCurrent) return candidateIsCurrent;
  }
  // Never profiled sorts below anything with a date, and two undated rows keep the first.
  return (candidate.profiled_at ?? "") > (held.profiled_at ?? "");
}

export function extractionStateOf(
  packageFormat: string,
  profile: ProfileResponse | undefined,
  capabilities: CapabilityIndex,
): ExtractionState {
  if (profile) {
    return profile.status === "failed"
      ? { kind: "failed", error: profile.error }
      : { kind: "read" };
  }
  const capability = capabilities.get(packageFormat);
  if (!capability) return { kind: "not_read", reason: "format_unsupported" };
  if (!capability.accepted) return { kind: "not_read", reason: "not_accepted" };
  return { kind: "not_read", reason: "unknown" };
}

/** How many of a set were read, and how many are in each exception. */
export function summarizeExtraction(states: ExtractionState[]) {
  return {
    read: states.filter((s) => s.kind === "read").length,
    failed: states.filter((s) => s.kind === "failed").length,
    notRead: states.filter((s) => s.kind === "not_read").length,
  };
}
