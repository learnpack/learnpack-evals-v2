import type { ScanCandidate, Uuid } from "@/lib/api/types";

/**
 * Whether a scanned candidate's own declared generator (LearnpackV2 only) agrees with what the
 * operator declared for the whole batch (ADR-0027 §5, ADR-0024).
 *
 * Computed on the client, from facts a scan never invalidates (`declared_generator_*`,
 * `resolved_generator_version_id`) against the operator's *current* selection — never from a
 * server-computed verdict, which would go stale the moment the operator changes the Card 1
 * selection without rescanning (the scan is explicitly not invalidated by that change).
 *
 * `"conflict"`: the operator declared a specific version and it disagrees with what the
 * package declares — blocks registration (the backend refuses it outright, no override).
 * `"notice"`: the operator declared `unknown` but the package declares something — informational
 * only, `unknown` stays legitimate (ADR-0024 cl. 1).
 */
export type DeclarationSignal = "conflict" | "notice" | null;

export function declarationSignal(
  candidate: Pick<
    ScanCandidate,
    "declared_generator_name" | "declared_generator_version" | "resolved_generator_version_id"
  >,
  selectedGeneratorVersionId: Uuid | null,
  generatorDeclared: boolean,
): DeclarationSignal {
  if (!candidate.declared_generator_name || !candidate.declared_generator_version) return null;
  if (!generatorDeclared) return null;
  if (selectedGeneratorVersionId === null) return "notice";
  if (selectedGeneratorVersionId === candidate.resolved_generator_version_id) return null;
  return "conflict";
}

/** Case/whitespace-insensitive only — a hint for the UI to offer a shortcut, never itself the
 *  authority on identity (the backend's `normalized_name` is, and re-checks at register time
 *  regardless). Good enough to decide whether to show "register this version" instead of
 *  "register this generator" without duplicating the domain rule on the client. */
export function looksLikeSameGeneratorName(a: string, b: string): boolean {
  return a.trim().replace(/\s+/g, " ").toLowerCase() === b.trim().replace(/\s+/g, " ").toLowerCase();
}
