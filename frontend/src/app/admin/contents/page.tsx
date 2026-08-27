"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { Boxes, ExternalLink, HardDrive, Pencil, Plus, Rows3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { ContentForm } from "@/components/admin/content-form";
import { CoursesByVersion } from "@/components/admin/courses-by-version";
import { GeneratorVersionPicker } from "@/components/admin/generator-version-picker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import {
  useAttributeGenerator,
  useBriefs,
  useContents,
  useDeclareConsumableUrl,
  useGeneratorVersions,
  useProfiles,
  useProfilingCapabilities,
} from "@/lib/api/hooks";
import type { ContentResponse, GeneratorVersionResponse } from "@/lib/api/types";
import { IS_LOCAL_AUTH } from "@/lib/auth";
import {
  extractionStateOf,
  indexCapabilities,
  indexProfiles,
  summarizeExtraction,
  type ExtractionState,
} from "@/lib/extraction";

const generatorName = (g?: GeneratorVersionResponse) => (g ? `${g.name} ${g.version}` : undefined);

/** The declared void of ADR-0024 as a filter value: courses whose generator is unknown are
 *  not a lineage, but they are the set an admin most often needs to isolate — to attribute
 *  them, or to see what generator-level accumulation is leaving out. */
const UNKNOWN_LINEAGE = "unknown";

const ALL = "";

export default function ContentsPage() {
  const { data: contents, isLoading, error } = useContents();
  // Brief and generator travel as ids on the content: resolved here so the two facts
  // that decide what a study can do with a course are readable — which commission it
  // shares (the pairing key) and whether its generator is known.
  const { data: briefs } = useBriefs();
  const { data: generators } = useGeneratorVersions();
  // Whether each course was read, from the two resources that already answer it. Neither is
  // required for the rest of the table: while they load, the column reads as unknown rather
  // than as a problem.
  const { data: profiles } = useProfiles();
  const { data: capabilities } = useProfilingCapabilities();
  const [creating, setCreating] = useState(false);
  // By version by default: it is the grain a round measures, and the one a person arrives
  // with. The flat list is the forensic view, and it keeps the filters.
  const [view, setView] = useState<"by-version" | "list">("by-version");
  const [format, setFormat] = useState(ALL);
  const [lineage, setLineage] = useState(ALL);
  const [version, setVersion] = useState(ALL);

  const briefById = useMemo(() => new Map((briefs ?? []).map((b) => [b.brief_id, b])), [briefs]);
  const generatorById = useMemo(
    () => new Map((generators ?? []).map((g) => [g.generator_version_id, g])),
    [generators],
  );

  const generatorOf = useCallback(
    (c: ContentResponse) =>
      c.generator_version_id ? generatorById.get(c.generator_version_id) : undefined,
    [generatorById],
  );

  const capabilityIndex = useMemo(() => indexCapabilities(capabilities), [capabilities]);
  const profileByContent = useMemo(
    () => indexProfiles(profiles, capabilityIndex),
    [profiles, capabilityIndex],
  );

  /** `null` until both answers are in: an empty profile list and a list still loading look
   *  the same, and rendering "not read" for every course while it loads would be a lie. */
  const extractionOf = useCallback(
    (c: ContentResponse): ExtractionState | null =>
      profiles === undefined || capabilities === undefined
        ? null
        : extractionStateOf(c.package_format, profileByContent.get(c.content_id), capabilityIndex),
    [profiles, capabilities, profileByContent, capabilityIndex],
  );

  // Every option below is derived from the registered courses, not from the full catalogue
  // of formats and lineages: an option that would return nothing is worse than no option.
  const formats = useMemo(
    () => [...new Set((contents ?? []).map((c) => c.package_format))].sort(),
    [contents],
  );

  const lineages = useMemo(() => {
    const byId = new Map<string, string>();
    for (const c of contents ?? []) {
      const g = generatorOf(c);
      if (g) byId.set(g.generator_id, g.name);
    }
    return [...byId].sort((a, b) => a[1].localeCompare(b[1]));
  }, [contents, generatorOf]);

  const hasUnknown = useMemo(
    () => (contents ?? []).some((c) => !c.generator_version_id),
    [contents],
  );

  // The second select exists only under a chosen lineage — `unknown` has no versions to
  // narrow, and a version means nothing without the lineage that names it.
  const versions = useMemo(() => {
    if (lineage === ALL || lineage === UNKNOWN_LINEAGE) return [];
    const byId = new Map<string, GeneratorVersionResponse>();
    for (const c of contents ?? []) {
      const g = generatorOf(c);
      if (g?.generator_id === lineage) byId.set(g.generator_version_id, g);
    }
    return [...byId.values()].sort((a, b) => a.version.localeCompare(b.version));
  }, [contents, generatorOf, lineage]);

  const visible = useMemo(
    () =>
      (contents ?? []).filter((c) => {
        if (format !== ALL && c.package_format !== format) return false;
        if (lineage === UNKNOWN_LINEAGE) return !c.generator_version_id;
        if (lineage !== ALL) {
          const g = generatorOf(c);
          if (g?.generator_id !== lineage) return false;
          if (version !== ALL && c.generator_version_id !== version) return false;
        }
        return true;
      }),
    [contents, format, generatorOf, lineage, version],
  );

  function chooseLineage(next: string) {
    setLineage(next);
    setVersion(ALL);
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Courses</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            AI-generated courses available to evaluate, grouped by the generator version that
            made them — which is the grain a round measures.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Local development only, and a build-time constant: the endpoints behind that
              page do not exist in any other mode, so the button never ships to one. */}
          {IS_LOCAL_AUTH ? (
            <Link href="/admin/measure" className={buttonVariants({ variant: "outline" })}>
              <HardDrive className="h-4 w-4" /> Import &amp; measure
            </Link>
          ) : null}
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Add course
          </Button>
        </div>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !contents || contents.length === 0 ? (
        <EmptyState title="No courses yet" hint="Add your first course to start a campaign." />
      ) : (
        <>
          {/* Not persisted on purpose: a stored preference is one more thing that can fall
              out of step with what the page shows, and coming back to the default view
              costs a click. */}
          <div className="mb-4 flex items-center gap-2">
            <Button
              size="sm"
              variant={view === "by-version" ? "secondary" : "ghost"}
              onClick={() => setView("by-version")}
            >
              <Boxes className="h-3.5 w-3.5" /> By version
            </Button>
            <Button
              size="sm"
              variant={view === "list" ? "secondary" : "ghost"}
              onClick={() => setView("list")}
            >
              <Rows3 className="h-3.5 w-3.5" /> List
            </Button>
          </div>

          {view === "by-version" ? (
            <CoursesByVersion
              contents={contents}
              generatorVersions={generators ?? []}
              extractionOf={extractionOf}
              onInspectUnknown={() => {
                setFormat(ALL);
                chooseLineage(UNKNOWN_LINEAGE);
                setView("list");
              }}
            />
          ) : (
            <>
          <div className="mb-4 flex flex-wrap items-end gap-3">
            <div className="w-48">
              <Label htmlFor="filter-format" className="text-xs text-muted-foreground">
                Format
              </Label>
              <Select
                id="filter-format"
                className="mt-1"
                value={format}
                onChange={(e) => setFormat(e.target.value)}
              >
                <option value={ALL}>All formats</option>
                {formats.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </Select>
            </div>
            <div className="w-56">
              <Label htmlFor="filter-lineage" className="text-xs text-muted-foreground">
                Generator
              </Label>
              <Select
                id="filter-lineage"
                className="mt-1"
                value={lineage}
                onChange={(e) => chooseLineage(e.target.value)}
              >
                <option value={ALL}>All generators</option>
                {lineages.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
                {hasUnknown ? <option value={UNKNOWN_LINEAGE}>unknown</option> : null}
              </Select>
            </div>
            <div className="w-40">
              <Label htmlFor="filter-version" className="text-xs text-muted-foreground">
                Version
              </Label>
              <Select
                id="filter-version"
                className="mt-1"
                value={version}
                disabled={versions.length === 0}
                onChange={(e) => setVersion(e.target.value)}
                title={
                  versions.length === 0 ? "Choose a generator to narrow it to a version." : undefined
                }
              >
                <option value={ALL}>All versions</option>
                {versions.map((g) => (
                  <option key={g.generator_version_id} value={g.generator_version_id}>
                    {g.version}
                  </option>
                ))}
              </Select>
            </div>
            {format !== ALL || lineage !== ALL ? (
              <Button
                variant="outline"
                onClick={() => {
                  setFormat(ALL);
                  chooseLineage(ALL);
                }}
              >
                Clear
              </Button>
            ) : null}
            <p className="ml-auto pb-2 text-sm text-muted-foreground">
              {visible.length} of {contents.length}
              <ExtractionSummary states={visible.map(extractionOf)} />
            </p>
          </div>

          {visible.length === 0 ? (
            <EmptyState
              title="No courses match these filters"
              hint="Widen the format or the generator to see more."
            />
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Course</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Format</TableHead>
                      <TableHead>Extraction</TableHead>
                      <TableHead>Brief</TableHead>
                      <TableHead>Generator</TableHead>
                      <TableHead>URL</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visible.map((c) => (
                      <TableRow key={c.content_id}>
                        <TableCell className="font-medium">{c.external_id}</TableCell>
                        <TableCell>{c.version}</TableCell>
                        <TableCell className="text-muted-foreground">{c.package_format}</TableCell>
                        <TableCell>
                          <ExtractionCell state={extractionOf(c)} format={c.package_format} />
                        </TableCell>
                        <TableCell className="max-w-xs">
                          {c.brief_id ? (
                            <span className="line-clamp-2 text-xs" title={c.brief_id}>
                              {briefById.get(c.brief_id)?.brief ?? c.brief_id}
                            </span>
                          ) : (
                            <span
                              className="text-xs text-muted-foreground"
                              title="No brief recorded: this course cannot enter a brief-paired dataset."
                            >
                              absent
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">
                          {c.generator_version_id ? (
                            <span
                              title={
                                c.generator_attributed_at
                                  ? `${c.generator_version_id} — attributed after registration on ${new Date(c.generator_attributed_at).toLocaleDateString()}`
                                  : c.generator_version_id
                              }
                            >
                              {generatorName(generatorById.get(c.generator_version_id)) ??
                                c.generator_version_id}
                              {c.generator_attributed_at ? (
                                <span className="ml-1 text-muted-foreground">
                                  (attributed later)
                                </span>
                              ) : null}
                            </span>
                          ) : (
                            <AttributeGeneratorCell content={c} />
                          )}
                        </TableCell>
                        <TableCell>
                          <DeploymentCell content={c} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
            </>
          )}
        </>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Register a course"
        description="Manually add an AI-generated course and its package artifacts."
      >
        <ContentForm onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}

const NOT_READ_REASON = {
  format_unsupported: (format: string) => `no adapter reads ${format}`,
  not_accepted: (format: string) => `${format} extraction is not accepted yet`,
  unknown: () => "profiling has not run on this package",
} as const;

/**
 * Whether one course was read.
 *
 * Only the exceptions get colour: a read course is the common case and asks nothing of
 * anyone, so it stays quiet — the same budget the profile workbench spends. And a course
 * with no profile is not the same as one the adapter choked on, so the two never share a
 * badge: one is work not done, the other is work that failed.
 */
function ExtractionCell({ state, format }: { state: ExtractionState | null; format: string }) {
  if (state === null) return <span className="text-xs text-muted-foreground">—</span>;
  if (state.kind === "read") return <span className="text-xs text-muted-foreground">read</span>;

  return (
    <div className="flex flex-col items-start gap-0.5">
      {state.kind === "failed" ? (
        <Badge variant="destructive" title={state.error ?? undefined}>
          could not be read
        </Badge>
      ) : (
        <Badge variant="warning">not read</Badge>
      )}
      <Link href="/admin/profiles" className="text-[11px] text-muted-foreground hover:underline">
        {state.kind === "failed"
          ? "see the error in Profiles"
          : `${NOT_READ_REASON[state.reason](format)} — Profiles`}
      </Link>
    </div>
  );
}

/** The exceptions among what is on screen. Counted over the visible rows, so it can never
 *  disagree with the filters right beside it — and silent while the answer is still loading. */
function ExtractionSummary({ states }: { states: (ExtractionState | null)[] }) {
  if (states.some((state) => state === null)) return null;
  const { failed, notRead } = summarizeExtraction(states as ExtractionState[]);
  if (failed === 0 && notRead === 0) return null;

  return (
    <>
      {" · "}
      <span className="font-medium text-foreground">
        {[
          notRead > 0 ? `${notRead} not read` : null,
          failed > 0 ? `${failed} could not be read` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </span>
    </>
  );
}

/** An unknown generator is a declared void — and the one thing that can still be filled,
 *  once (ADR-0024). Everything else about a registered content stays immutable. */
function AttributeGeneratorCell({ content }: { content: ContentResponse }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("");
  const attribute = useAttributeGenerator();

  function submit() {
    attribute.mutate(
      { contentId: content.content_id, body: { generator_version_id: selected } },
      {
        onSuccess: () => {
          setOpen(false);
          toast.success("Generator attributed.");
        },
        onError: (err) => {
          const e = err as ApiError;
          setOpen(false);
          if (e.status === 409) {
            toast.error("This course already has a generator — attribution never replaces one.");
          } else {
            toast.error("Could not attribute.", { description: e.message });
          }
        },
      },
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
        title="Declared unknown: excluded from generator-level accumulation. Attribute one if you learn it."
      >
        unknown
      </button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={`Attribute a generator to ${content.external_id}`}
        description="Records a generator learnt after registration. It fills the declared unknown once and cannot be changed afterwards."
      >
        {/* No unknown option: attributing IS naming the version, so the answer this act
            exists to record is the only one it can take. */}
        <GeneratorVersionPicker
          value={selected}
          onChange={setSelected}
          allowUnknown={false}
          className="sm:grid-cols-1"
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={attribute.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!selected || attribute.isPending}>
            {attribute.isPending ? <Spinner /> : null} Attribute
          </Button>
        </div>
      </Dialog>
    </>
  );
}

/**
 * What this course declares about its deployment — and the act that changes it (ADR-0054).
 *
 * Both states carry the act, and that is the whole point. Filling the void is what a course
 * registered from a local source needs before a human can be put in front of it; redeclaring
 * is what a course that moved needs, and a console offering only the first would leave a dead
 * link repairable nowhere but the CLI — the hole ADR-0054 closed, recreated one level up.
 *
 * Unlike the generator next door, which is attributed once and never replaced: a generator
 * link is a discovery, a deployment is a statement about the world right now.
 */
function DeploymentCell({ content }: { content: ContentResponse }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const declare = useDeclareConsumableUrl();

  const current = content.consumable_url;
  const typed = url.trim();
  // Declaring the URL a course already has writes nothing and emits nothing (ADR-0054 §3),
  // so the screen does not offer it: a button that promises an act must perform one.
  const unchanged = typed === (current ?? "");

  function start() {
    setUrl(current ?? "");
    setOpen(true);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    declare.mutate(
      { contentId: content.content_id, body: { consumable_url: typed } },
      {
        onSuccess: () => {
          setOpen(false);
          toast.success(current ? "Deployment redeclared." : "Deployment declared.");
        },
        onError: (err) => {
          const e = err as ApiError;
          setOpen(false);
          if (e.status === 404) {
            toast.error("This course is no longer registered.");
          } else if (e.status === 409) {
            toast.error("Somebody declared a different URL first.", {
              description: "The row has been refreshed — read it and declare again.",
            });
          } else if (e.status === 422) {
            toast.error("A deployment must be an http(s) URL.");
          } else {
            toast.error("Could not declare.", { description: e.message });
          }
        },
      },
    );
  }

  return (
    <>
      {current ? (
        <span className="inline-flex items-center gap-2">
          <a
            href={current}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            Open <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <button
            type="button"
            onClick={start}
            className="text-muted-foreground hover:text-foreground"
            title="Redeclare: a deployment that moved otherwise keeps a dead link."
          >
            <Pencil className="h-3.5 w-3.5" />
            <span className="sr-only">Redeclare the deployment</span>
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={start}
          className="text-xs text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
          title="No deployed instance declared: this course can be evaluated automatically, but not by a human. Declare one if it exists."
        >
          none
        </button>
      )}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={`${current ? "Redeclare" : "Declare"} the deployment of ${content.external_id}`}
        description={
          current
            ? "Points this course at where it is deployed now. The URL it is moving from is recorded with it, so a judgement made against the old one stays reconstructible."
            : "Points this course at a deployed, human-consumable instance of it. Without one it can be evaluated automatically, but never by a person."
        }
      >
        <form onSubmit={submit} className="space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="consumable-url">Deployed instance</Label>
            <Input
              id="consumable-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://…"
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={declare.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={!typed || unchanged || declare.isPending}>
              {declare.isPending ? <Spinner /> : null} {current ? "Redeclare" : "Declare"}
            </Button>
          </div>
        </form>
      </Dialog>
    </>
  );
}
