"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Quote, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { ReadPackagesButton } from "@/components/admin/read-packages-button";
import { ApiError } from "@/lib/api/client";
import {
  useAcceptExtraction,
  useContents,
  useProfiles,
  useProfilingCapabilities,
} from "@/lib/api/hooks";
import { describeLocator } from "@/lib/locator";
import type {
  ContentResponse,
  ProfileCapabilitiesResponse,
  ProfileEntryResponse,
  ProfileResponse,
} from "@/lib/api/types";

/**
 * The designer's workbench: the screen someone reads to decide whether an extraction
 * adapter can be trusted — the judgement the `accept-extraction` act records.
 *
 * Two rules of the domain drive the visual weight here, and neither is decoration:
 *
 * 1. **Absence is a finding, not a failure.** A course that declares no objectives is
 *    telling us something true about its generator. So `absent` is never red; it is drawn
 *    as literal emptiness — an unfilled stretch of the provenance bar, a dashed entry card.
 * 2. **Only exceptions get colour.** A successful profile is the common case and carries no
 *    action, so it gets no badge: the provenance bar IS the evidence that it worked. The
 *    colour budget is spent on `failed`, which is the only row anyone has to do something
 *    about.
 */
export default function ProfilesPage() {
  const { data: profiles, isLoading, error } = useProfiles();
  const { data: capabilities } = useProfilingCapabilities();
  // What is registered but has no profile — the backlog the band offers to read. Nothing
  // profiles it retroactively when a format is accepted, so it would otherwise stay unread
  // for good.
  const { data: contents } = useContents();

  // Failures first — a broken extraction buried under twenty good ones is a failure the
  // page is hiding. Then by course, so the order is stable between visits.
  const ordered = useMemo(
    () =>
      [...(profiles ?? [])].sort((a, b) => {
        if (a.status !== b.status) return a.status === "failed" ? -1 : 1;
        return (a.external_id ?? a.content_id).localeCompare(b.external_id ?? b.content_id);
      }),
    [profiles],
  );
  const failed = ordered.filter((p) => p.status === "failed").length;

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Content profiles</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          What the extraction adapters read out of each course package, quoted verbatim.
          Nothing here is inferred: when a course does not declare something, the profile
          records it as <span className="font-medium text-foreground">absent</span> — a
          finding about the course, not a gap in the extraction.
        </p>
      </div>

      <ExtractionStatus capabilities={capabilities} profiles={profiles} contents={contents} />

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : ordered.length === 0 ? (
        <EmptyState
          title="No courses have been read yet"
          hint="With the extraction accepted, registering a course reads it on the spot. Anything registered before that is waiting — the band above offers to read it."
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            {ordered.length} {ordered.length === 1 ? "profile" : "profiles"}
            {failed > 0 ? (
              <>
                {" · "}
                <span className="font-medium text-destructive">
                  {failed} failed {failed === 1 ? "extraction" : "extractions"}, listed first
                </span>
              </>
            ) : (
              ", all extracted"
            )}
          </p>
          <div className="space-y-3">
            {ordered.map((profile) => (
              <ProfileCard key={profile.profile_id} profile={profile} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Whether each format's current adapter version is trusted, and the two acts that move it.
 *
 * Inverted emphasis on purpose: "accepted" is the resting state and stays quiet, while "not
 * accepted" is the one that changes what the system does — automatic profiling stays off —
 * so it carries the colour and the act.
 *
 * The order of the two acts is the order the domain requires. Reading packages by hand is
 * how the samples that earn an acceptance are produced, so *Read them now* comes first and
 * *Accept* is taken afterwards, over evidence that is on this very page. That is also why
 * neither act appears anywhere else: a button to accept on a screen with no profiles would
 * invite an irreversible judgement with nothing to read.
 */
function ExtractionStatus({
  capabilities,
  profiles,
  contents,
}: {
  capabilities: ProfileCapabilitiesResponse[] | undefined;
  profiles: ProfileResponse[] | undefined;
  contents: ContentResponse[] | undefined;
}) {
  const [accepting, setAccepting] = useState<ProfileCapabilitiesResponse | null>(null);
  if (!capabilities || capabilities.length === 0) return null;

  const profiled = new Set((profiles ?? []).map((p) => p.content_id));
  const unreadOf = (format: string) =>
    (contents ?? []).filter((c) => c.package_format === format && !profiled.has(c.content_id));

  return (
    <div className="mb-6 space-y-3 rounded-lg border bg-muted/30 px-4 py-3">
      {capabilities.map((capability) => {
        const unread = unreadOf(capability.package_format);
        return (
          <div
            key={capability.package_format}
            className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm"
          >
            <span className="font-medium">{capability.package_format}</span>
            <span className="text-muted-foreground">adapter v{capability.adapter_version}</span>
            {capability.accepted ? (
              <span className="text-xs text-muted-foreground">extraction accepted</span>
            ) : (
              <Badge variant="warning">not accepted yet</Badge>
            )}

            <span className="ml-auto flex flex-wrap items-center gap-2">
              {unread.length > 0 ? (
                <ReadPackagesButton
                  label={`Read ${unread.length} waiting`}
                  contentIds={unread.map((c) => c.content_id)}
                />
              ) : null}
              {capability.accepted ? null : (
                <Button size="sm" onClick={() => setAccepting(capability)}>
                  <ShieldCheck className="h-3.5 w-3.5" /> Accept extraction
                </Button>
              )}
            </span>
          </div>
        );
      })}

      {capabilities.some((c) => !c.accepted) ? (
        <p className="text-xs text-muted-foreground">
          Registering a course does not profile it until someone accepts the adapter version
          that reads it. Read a few by hand first — those profiles are the evidence the
          acceptance rests on.
        </p>
      ) : null}

      <AcceptExtractionDialog
        capability={accepting}
        unread={accepting ? unreadOf(accepting.package_format).length : 0}
        reviewed={
          accepting
            ? (profiles ?? []).filter((p) => p.package_format === accepting.package_format).length
            : 0
        }
        onClose={() => setAccepting(null)}
      />
    </div>
  );
}

/**
 * The irreversible one, behind a dialog that states what is being committed to rather than
 * asking whether you are sure — the shape the console already uses for publishing an
 * instrument and ratifying an assessor.
 *
 * It never blocks on having read nothing: readiness informs. It says so instead, because a
 * format accepted over zero profiles is an acceptance of nothing.
 */
function AcceptExtractionDialog({
  capability,
  reviewed,
  unread,
  onClose,
}: {
  capability: ProfileCapabilitiesResponse | null;
  reviewed: number;
  unread: number;
  onClose: () => void;
}) {
  const accept = useAcceptExtraction();
  if (capability === null) return null;

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Accept ${capability.package_format} extraction?`}
      description="This is what lets anyone reading a result rule out broken extraction as the explanation."
    >
      <ul className="space-y-2 text-sm">
        <li className="rounded border p-2">
          <span className="font-medium">
            Adapter v{capability.adapter_version} becomes trusted for {capability.package_format}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            From here, registering a course in this format profiles it on the spot. Accepting
            is recorded with your name and is not undone — a different extraction is a new
            adapter version.
          </span>
        </li>
        <li className="rounded border p-2">
          <span className="font-medium">
            {reviewed === 0
              ? "Nothing has been read in this format yet"
              : `${reviewed} profile${reviewed === 1 ? "" : "s"} on this page to judge it by`}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            {reviewed === 0
              ? "Nothing is stopping you, but an acceptance over no evidence says nothing. Read a few first."
              : "Accepting says those extractions are trustworthy enough to stop being a suspect."}
            {unread > 0
              ? ` ${unread} course${unread === 1 ? "" : "s"} in this format stay${unread === 1 ? "s" : ""} unread until somebody reads ${unread === 1 ? "it" : "them"} — accepting does not go back over what is already registered.`
              : ""}
          </span>
        </li>
      </ul>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={accept.isPending}>
          Cancel
        </Button>
        <Button
          disabled={accept.isPending}
          onClick={() =>
            accept.mutate(capability.package_format, {
              onSuccess: (result) => {
                toast.success(
                  result.newly_accepted
                    ? `${capability.package_format} extraction accepted.`
                    : `${capability.package_format} was already accepted.`,
                );
                onClose();
              },
              onError: (err) =>
                toast.error("Could not accept the extraction.", {
                  description: (err as ApiError).message,
                }),
            })
          }
        >
          {accept.isPending ? <Spinner /> : null} Accept extraction
        </Button>
      </div>
    </Dialog>
  );
}

const PROVENANCE_LABEL = {
  declared_structured: "declared (structured)",
  declared_in_content: "declared in content",
  absent: "absent",
} as const;

type Provenance = keyof typeof PROVENANCE_LABEL;

function countProvenances(entries: ProfileEntryResponse[]): Record<Provenance, number> {
  const counts: Record<Provenance, number> = {
    declared_structured: 0,
    declared_in_content: 0,
    absent: 0,
  };
  for (const entry of entries) counts[entry.provenance] += 1;
  return counts;
}

/**
 * The shape of one profile's evidence, at a glance: how much the course declared in a
 * structured field, how much it stated in prose, and how much it did not state at all.
 *
 * Comparing these bars down the page is the adapter-trust judgement this screen exists for —
 * a column of near-empty bars means the adapter is not finding what it should, or the
 * generator is not declaring it, and either is worth knowing before accepting the extraction.
 *
 * Two fills and a void: absent is the unfilled track, never a colour, because it is not an
 * error. Both fills are `primary`, which flips light-on-dark with the theme, so "more filled
 * = more evidence" survives dark mode without a second palette.
 */
function ProvenanceBar({ counts, total }: { counts: Record<Provenance, number>; total: number }) {
  if (total === 0) return null;
  const percent = (n: number) => `${(n / total) * 100}%`;

  // aria-hidden: the counts printed beside it say the same thing in words, and a screen
  // reader gains nothing from two renderings of one fact.
  return (
    <span aria-hidden className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-muted sm:flex">
      <span className="bg-primary" style={{ width: percent(counts.declared_structured) }} />
      <span className="bg-primary/45" style={{ width: percent(counts.declared_in_content) }} />
    </span>
  );
}

function ProfileCard({ profile }: { profile: ProfileResponse }) {
  const counts = countProvenances(profile.entries);
  const declared = counts.declared_structured + counts.declared_in_content;
  const failed = profile.status === "failed";

  return (
    <CollapsibleSection
      defaultOpen={false}
      title={profile.external_id ?? profile.content_id}
      badge={
        <>
          v{profile.content_version ?? "?"} · {profile.package_format}/{profile.adapter_version}
        </>
      }
      meta={
        failed ? (
          <Badge variant="destructive">failed</Badge>
        ) : (
          <>
            <ProvenanceBar counts={counts} total={profile.entries.length} />
            <span className="text-xs tabular-nums text-muted-foreground">
              {declared} of {profile.entries.length} declared
            </span>
          </>
        )
      }
    >
      {failed ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <p className="font-medium">The adapter could not read this package</p>
          <p className="mt-1 text-muted-foreground">{profile.error}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <ReadPackagesButton label="Try again" contentIds={[profile.content_id]} />
            <p className="text-xs text-muted-foreground">
              Fix the package or the adapter first — a failed profile is replaced in place, and
              nothing else ever retries it.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <ProvenanceLegend counts={counts} profiledAt={profile.profiled_at} />
          {profile.entries.map((entry) => (
            <ProfileEntry key={entry.data_requirement_id} entry={entry} />
          ))}
          {profile.extras.length > 0 ? (
            <div className="rounded-md border border-dashed p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Extras (out of contract)
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {profile.extras.map((extra) => (
                  <li key={extra.name}>
                    <span className="font-medium">{extra.name}</span>:{" "}
                    {JSON.stringify(extra.value)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </CollapsibleSection>
  );
}

/** The bar's key, spelled out once per open profile — and when the extraction ran. */
function ProvenanceLegend({
  counts,
  profiledAt,
}: {
  counts: Record<Provenance, number>;
  profiledAt: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b pb-3 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-sm bg-primary" />
        {counts.declared_structured} {PROVENANCE_LABEL.declared_structured}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-sm bg-primary/45" />
        {counts.declared_in_content} {PROVENANCE_LABEL.declared_in_content}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-sm border border-dashed border-muted-foreground/60" />
        {counts.absent} absent
      </span>
      {profiledAt ? (
        <span className="ml-auto">extracted {new Date(profiledAt).toLocaleString()}</span>
      ) : null}
    </div>
  );
}

function ProfileEntry({ entry }: { entry: ProfileEntryResponse }) {
  const absent = entry.provenance === "absent";
  const [showQuote, setShowQuote] = useState(false);
  return (
    <div className={`rounded-md border p-3 ${absent ? "border-dashed bg-muted/30" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{entry.data_requirement_id}</span>
        <Badge variant={absent ? "outline" : "secondary"}>
          {PROVENANCE_LABEL[entry.provenance]}
        </Badge>
      </div>
      {absent ? (
        <p className="mt-1 text-sm text-muted-foreground">
          The course does not declare this — a finding, not a gap in extraction.
        </p>
      ) : (
        <>
          <pre className="mt-2 overflow-x-auto rounded bg-muted/40 p-2 text-xs">
            {JSON.stringify(entry.value, null, 2)}
          </pre>
          <p className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Quote className="h-3 w-3 shrink-0" />
            <span>extracted from: {describeLocator(entry.locator)}</span>
            {entry.quote ? (
              <button
                type="button"
                onClick={() => setShowQuote(!showQuote)}
                aria-expanded={showQuote}
                className="rounded text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {showQuote ? "hide verbatim quote" : "show verbatim quote"}
              </button>
            ) : null}
          </p>
          {showQuote && entry.quote ? (
            <p className="mt-1 rounded bg-muted/30 p-2 text-xs italic text-muted-foreground">
              {entry.quote}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
