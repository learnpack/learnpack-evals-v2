"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Play, Unlock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useBriefs,
  useContents,
  useDeclareStudy,
  useGeneratorVersions,
  useInstruments,
  useMatchings,
  useOpenStudy,
  useStartRound,
  useUpdateStudyDraft,
} from "@/lib/api/hooks";
import type {
  AssessorPackageResponse,
  GeneratorScope,
  GeneratorVersionResponse,
  StudyResponse,
  Uuid,
} from "@/lib/api/types";

/** One form builds a study, in two states: without an id and with one.
 *
 *  They were the same form rendered twice with different affordances — a dialog that asked
 *  for a name, and a card of four numbered steps that asked for everything else — so they
 *  are one component now. Nothing here is binding: the instrument, the judge and the
 *  courses replace freely, and OPENING is what pins them (ADR-0043 §1). That is why the
 *  word "pin" appears nowhere on the screen and the guarantee is stated once, in the
 *  dialog behind the only irreversible button.
 *
 *  The order of the fields is the one real dependency between them: the judge list is
 *  filtered by ratification against the chosen instrument, and the courses are annotated
 *  against what that instrument can read.
 */
export function StudyForm({ study }: { study?: StudyResponse }) {
  const router = useRouter();
  const instruments = useInstruments();
  const packages = useAssessorPackages();
  const briefs = useBriefs();
  const contents = useContents();
  const generatorVersions = useGeneratorVersions();

  const declare = useDeclareStudy();
  const update = useUpdateStudyDraft();
  const openStudy = useOpenStudy();
  const startRound = useStartRound();

  const [name, setName] = useState(study?.name ?? "");
  const [description, setDescription] = useState(study?.description ?? "");
  const [instrumentId, setInstrumentId] = useState(study?.instrument_version_id ?? "");
  const [assessorId, setAssessorId] = useState<string>(study?.assessor_id ?? "");
  const [briefIds, setBriefIds] = useState<Uuid[]>(study?.brief_ids ?? []);
  // `null` is "nobody has said yet", which is exactly what the study carries and what
  // opening refuses (ADR-0044 §2). It is never collapsed into "all" on anyone's behalf.
  const [scope, setScope] = useState<GeneratorScope | null>(study?.generator_scope ?? null);
  const [confirming, setConfirming] = useState(false);

  const published = (instruments.data ?? []).filter((i) => i.status === "published");
  const eligible = ratifiedFor(packages.data ?? [], instrumentId);
  const chosenAssessor = (packages.data ?? []).find((pkg) => pkg.assessor_id === assessorId);

  // Courses per brief, from what is registered — narrowed by the scope, because the recipe
  // has two axes and the backend materializes their intersection. The count on screen is
  // the count that will run, which is only true if this filter matches that one: a listed
  // scope drops the unknown-generator courses too, as `= ANY` does (ADR-0044 §6).
  const coursesByBrief = useMemo(() => {
    const grouped = new Map<Uuid, Course[]>();
    for (const content of contents.data ?? []) {
      if (content.brief_id === null) continue;
      if (Array.isArray(scope)) {
        if (content.generator_version_id === null) continue;
        if (!scope.includes(content.generator_version_id)) continue;
      }
      grouped.set(content.brief_id, [
        ...(grouped.get(content.brief_id) ?? []),
        { format: content.package_format, versionId: content.generator_version_id },
      ]);
    }
    return grouped;
  }, [contents.data, scope]);

  const selectedCourses = briefIds.flatMap((id) => coursesByBrief.get(id) ?? []);
  const formats = [...new Set(selectedCourses.map((c) => c.format))].sort();
  const matchings = useMatchings(instrumentId || null, formats);

  /** The versions this round will actually measure, in the order they are named. A listed
   *  scope says so itself; `"all"` is only knowable from what the briefs brought, and a
   *  version present in the registry but absent from the dataset is not one of them. */
  const arms = armsOf(scope, selectedCourses, generatorVersions.data ?? []);

  // An empty list is a radio ticked and nothing chosen yet — not a declaration, and the API
  // refuses it. It reads as "still missing" rather than as a request that will fail.
  const scopeDeclared = scope === "all" || (Array.isArray(scope) && scope.length > 0);
  const complete = Boolean(
    name.trim() && instrumentId && assessorId && scopeDeclared && selectedCourses.length,
  );
  const busy =
    declare.isPending || update.isPending || openStudy.isPending || startRound.isPending;

  /** Re-pointing at a norm the current judge never ratified drops the judge, here rather
   *  than in the request: the endpoint refuses that pair instead of guessing which of the
   *  two was meant, and the person who knows is the one who just changed the field. */
  function chooseInstrument(next: string) {
    setInstrumentId(next);
    if (assessorId && !ratifiedFor(packages.data ?? [], next).some((p) => p.assessor_id === assessorId)) {
      setAssessorId("");
      if (next) toast.info("The judge was cleared: it has not ratified that version.");
    }
  }

  function toggleBrief(id: Uuid) {
    setBriefIds((prev) => (prev.includes(id) ? prev.filter((b) => b !== id) : [...prev, id]));
  }

  /** Create or update, and answer with the study either way — the two differ in one verb. */
  async function save(): Promise<StudyResponse | null> {
    const body = {
      name: name.trim(),
      description: description.trim() || null,
      instrument_version_id: instrumentId || undefined,
      assessor_id: (assessorId || null) as Uuid | null,
      brief_ids: briefIds,
      // Omitted while undeclared: absent leaves it alone, and `null` would be refused —
      // there is no way to say "un-declare", by design.
      generator_scope: scopeDeclared ? (scope as GeneratorScope) : undefined,
    };
    try {
      if (study) {
        return await update.mutateAsync({ studyId: study.study_id, body });
      }
      return await declare.mutateAsync(body);
    } catch (err) {
      toast.error("Could not save the study.", { description: (err as ApiError).message });
      return null;
    }
  }

  async function saveDraft() {
    const saved = await save();
    if (!saved) return;
    toast.success("Draft saved.", { description: "Nothing is fixed yet — come back any time." });
    if (!study) router.push(`/admin/studies/${saved.study_id}`);
  }

  /** Save, open, evaluate — three requests on purpose. A failure in the middle leaves a
   *  valid draft, which is the state this whole redesign exists to make safe; a compound
   *  endpoint would trade that away for one round trip. */
  async function saveAndEvaluate() {
    const saved = await save();
    if (!saved) return;
    try {
      await openStudy.mutateAsync({ studyId: saved.study_id });
    } catch (err) {
      setConfirming(false);
      toast.error("Saved, but the round did not start.", {
        description: (err as ApiError).message,
      });
      if (!study) router.push(`/admin/studies/${saved.study_id}`);
      return;
    }
    try {
      await startRound.mutateAsync({ studyId: saved.study_id, body: { re_evaluate: false } });
      toast.success("Evaluating", { description: "It reports as it goes, and can be stopped." });
    } catch (err) {
      toast.error("The round is open, but the batch did not start.", {
        description: (err as ApiError).message,
      });
    }
    setConfirming(false);
    router.push(`/admin/studies/${saved.study_id}`);
  }

  return (
    <Card>
      <CardContent className="space-y-6 pt-6">
        <Field id="study-name" label="Name" hint="Names the round for whoever reads its report later.">
          <Input
            id="study-name"
            autoFocus={!study}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. LearnpackV2 — first QA round"
          />
        </Field>

        <Field
          id="study-description"
          label="Description"
          optional
          hint="What this round is for, and what you expect to learn from it."
        >
          <Textarea
            id="study-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Does the 2.0.0 generator hold the drafts bar the 1.x one set?"
          />
        </Field>

        <hr className="border-border" />

        <Field
          id="study-instrument"
          label="Instrument"
          hint="The published version this round judges against. It decides which judges and which course formats can take part."
        >
          <Select
            id="study-instrument"
            className="max-w-md"
            value={instrumentId}
            onChange={(e) => chooseInstrument(e.target.value)}
          >
            <option value="">Choose an instrument…</option>
            {published.map((i) => (
              <option key={i.instrument_version_id} value={i.instrument_version_id}>
                {i.instrument_version_id}
              </option>
            ))}
          </Select>
        </Field>

        <Field
          id="study-judge"
          label="Judge"
          hint="Whose verdicts are this round's result. Only judges that have ratified the chosen version can take part."
        >
          <JudgeField
            instrumentId={instrumentId}
            eligible={eligible}
            value={assessorId}
            onChange={setAssessorId}
          />
        </Field>

        <Field
          id="study-scope"
          label="Generator versions"
          hint="What this round measures. One version is a measurement of that version; several are a comparison between them."
        >
          <ScopeField
            versions={generatorVersions.data ?? []}
            value={scope}
            onChange={setScope}
          />
          {scope === "all" && arms.length > 1 ? (
            <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
              These briefs brought courses from {arms.length} versions (
              {arms.map((arm) => arm.label).join(", ")}), and the round&apos;s own header will
              read them as one population. Legitimate, and said here rather than discovered in
              the report — naming the versions instead separates them.
            </p>
          ) : null}
        </Field>

        <Field
          id="study-courses"
          label="Courses"
          hint="Picked by brief — each brief brings the courses registered from it, narrowed to the versions above."
        >
          <div className="space-y-2">
            {(briefs.data ?? []).length === 0 ? (
              <p className="rounded border bg-muted/40 p-2 text-xs text-muted-foreground">
                No briefs registered yet. Briefs arrive mechanically when contents with a
                syllabus are registered (ADR-0022), or manually in /admin/briefs.
              </p>
            ) : (
              (briefs.data ?? []).map((brief) => {
                const courses = coursesByBrief.get(brief.brief_id) ?? [];
                return (
                  <BriefRow
                    key={brief.brief_id}
                    text={brief.brief}
                    courses={courses}
                    arms={arms}
                    checked={briefIds.includes(brief.brief_id)}
                    unreadableIn={(format) => unreadableCount(matchings.byFormat.get(format))}
                    onToggle={() => toggleBrief(brief.brief_id)}
                  />
                );
              })
            )}
            <UnpairedCommissions
              briefs={(briefs.data ?? [])
                .filter((brief) => briefIds.includes(brief.brief_id))
                .map((brief) => ({
                  text: brief.brief,
                  courses: coursesByBrief.get(brief.brief_id) ?? [],
                }))}
              arms={arms}
            />
            <ArmCoverage
              arms={arms}
              unreadableIn={(format) => unreadableCount(matchings.byFormat.get(format))}
            />
            <PartialCoverage
              formats={formats}
              courses={selectedCourses}
              unreadableIn={(format) => unreadableCount(matchings.byFormat.get(format))}
            />
          </div>
        </Field>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <p className="max-w-lg text-xs text-muted-foreground">
            {complete
              ? `${selectedCourses.length} course${selectedCourses.length === 1 ? "" : "s"} · ${scopeSummary(arms)} · judged by ${chosenAssessor?.display_name ?? assessorId} · against ${instrumentId}`
              : `Still missing ${missing(name, instrumentId, assessorId, scopeDeclared, selectedCourses.length).join(", ")}.`}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="ghost" onClick={() => router.push("/admin/studies")} disabled={busy}>
              Cancel
            </Button>
            <Button variant="outline" onClick={saveDraft} disabled={busy || !name.trim()}>
              {update.isPending || declare.isPending ? <Spinner /> : null} Save draft
            </Button>
            <Button onClick={() => setConfirming(true)} disabled={busy || !complete}>
              <Play className="h-3.5 w-3.5" /> Save &amp; evaluate
            </Button>
          </div>
        </div>

        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <Unlock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Saving as a draft commits you to nothing. A draft can be renamed, re-pointed at
            another instrument and re-composed for as long as it stays a draft.
          </span>
        </p>
      </CardContent>

      {/* Outside anything that could unmount mid-flight, like every other act in the console. */}
      <ConfirmRound
        open={confirming}
        onClose={() => setConfirming(false)}
        name={name.trim()}
        instrumentId={instrumentId}
        assessor={chosenAssessor}
        courses={selectedCourses.length}
        arms={arms}
        pending={busy}
        onConfirm={saveAndEvaluate}
      />
    </Card>
  );
}

// ------------------------------------------------------------------------------ fields

function Field({
  id,
  label,
  hint,
  optional,
  children,
}: {
  id: string;
  label: string;
  hint: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {label}
        {optional ? <span className="ml-1 font-normal text-muted-foreground">(optional)</span> : null}
      </Label>
      <p className="text-xs text-muted-foreground">{hint}</p>
      {children}
    </div>
  );
}

/** Filtered by RATIFICATION, not by existence: an assessor that has not ratified would be
 *  refused by the endpoint, and an option that cannot work is worse than no option
 *  (ADR-0036). The empty case says what to do about it instead of showing an empty list. */
function JudgeField({
  instrumentId,
  eligible,
  value,
  onChange,
}: {
  instrumentId: string;
  eligible: AssessorPackageResponse[];
  value: string;
  onChange: (id: string) => void;
}) {
  if (!instrumentId) {
    return (
      <p className="rounded border bg-muted/40 p-2 text-xs text-muted-foreground">
        Choose an instrument first — the list of judges depends on it.
      </p>
    );
  }
  if (eligible.length === 0) {
    return (
      <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
        No judge has ratified <code>{instrumentId}</code> yet. Ratifying is a human act and
        lives in /admin/assessors — until it happens, no verdict on this version can be kept.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {eligible.map((pkg) => (
        <label
          key={pkg.assessor_id ?? pkg.name}
          className="flex cursor-pointer items-start gap-2 rounded border p-2 text-sm hover:bg-muted/50"
        >
          <input
            type="radio"
            name="study-judge"
            className="mt-1"
            checked={value === pkg.assessor_id}
            onChange={() => onChange(pkg.assessor_id ?? "")}
          />
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              {pkg.display_name}
              {pkg.uses_llm ? (
                <Badge variant="warning">spends LLM calls</Badge>
              ) : (
                <Badge variant="success">free</Badge>
              )}
            </span>
            <span className="block text-xs text-muted-foreground">
              {pkg.executes.length} criteria executed
              {Object.keys(pkg.abstains).length > 0
                ? ` · ${Object.keys(pkg.abstains).length} left to another judge`
                : ""}
            </span>
          </span>
        </label>
      ))}
    </div>
  );
}

/** The recipe's second axis, asked as what it is: a declaration with two forms and no third
 *  (ADR-0044 §1). There is deliberately no pre-selected option — "every version" is a thing
 *  somebody says, and a default would say it for them, which is the whole defect. */
function ScopeField({
  versions,
  value,
  onChange,
}: {
  versions: GeneratorVersionResponse[];
  value: GeneratorScope | null;
  onChange: (next: GeneratorScope) => void;
}) {
  const listed = Array.isArray(value) ? value : [];

  function toggle(id: Uuid) {
    const next = listed.includes(id) ? listed.filter((v) => v !== id) : [...listed, id];
    // An empty list selects nothing and the API refuses it — so emptying the last checkbox
    // returns the field to undeclared rather than sending a scope that cannot be honoured.
    onChange(next.length ? next : []);
  }

  return (
    <div className="space-y-2">
      <label className="flex cursor-pointer items-start gap-2 rounded border p-2 text-sm hover:bg-muted/50">
        <input
          type="radio"
          name="study-scope"
          className="mt-1"
          checked={value === "all"}
          onChange={() => onChange("all")}
        />
        <span>
          Every version
          <span className="block text-xs text-muted-foreground">
            All the courses these briefs brought, whichever version made them. If that is more
            than one, the round pools them and its report reads as a single population.
          </span>
        </span>
      </label>

      <label className="flex cursor-pointer items-start gap-2 rounded border p-2 text-sm hover:bg-muted/50">
        <input
          type="radio"
          name="study-scope"
          className="mt-1"
          checked={Array.isArray(value)}
          onChange={() => onChange([])}
        />
        <span>
          These versions
          <span className="block text-xs text-muted-foreground">
            Courses from the versions you tick, and no others.
          </span>
        </span>
      </label>

      {Array.isArray(value) ? (
        versions.length === 0 ? (
          <p className="rounded border bg-muted/40 p-2 text-xs text-muted-foreground">
            No generator versions registered yet — they live in /admin/generators.
          </p>
        ) : (
          <div className="ml-6 space-y-1">
            {versions.map((version) => (
              <label
                key={version.generator_version_id}
                className="flex cursor-pointer items-center gap-2 rounded border p-2 text-sm hover:bg-muted/50"
              >
                <input
                  type="checkbox"
                  checked={listed.includes(version.generator_version_id)}
                  onChange={() => toggle(version.generator_version_id)}
                />
                <span>
                  {version.name} {version.version}
                </span>
              </label>
            ))}
            {listed.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Tick at least one — an empty list would select nothing.
              </p>
            ) : null}
          </div>
        )
      ) : null}
    </div>
  );
}

/** One commission, and what it brought per version once more than one is being measured.
 *  A version with no course from this brief is shown as a zero rather than left out: an
 *  unpaired commission is a fact about the comparison, and this is the last moment anyone
 *  can act on it (the shape ADR-0039 already settled for the report). */
function BriefRow({
  text,
  courses,
  arms,
  checked,
  unreadableIn,
  onToggle,
}: {
  text: string;
  courses: Course[];
  arms: Arm[];
  checked: boolean;
  unreadableIn: (format: string) => number | null;
  onToggle: () => void;
}) {
  const byFormat = new Map<string, number>();
  for (const course of courses) byFormat.set(course.format, (byFormat.get(course.format) ?? 0) + 1);
  const empty = courses.length === 0;
  const comparing = arms.length > 1;

  return (
    <label
      className={`flex cursor-pointer items-start gap-2 rounded border p-2 text-sm hover:bg-muted/50 ${
        empty ? "opacity-60" : ""
      }`}
    >
      <input type="checkbox" className="mt-1" checked={checked} disabled={empty} onChange={onToggle} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className="line-clamp-2">{text}</span>
          {[...byFormat.keys()].map((format) => {
            const unreadable = unreadableIn(format);
            return unreadable ? (
              <Badge key={format} variant="warning">
                partial on {format}
              </Badge>
            ) : null;
          })}
        </span>
        <span className="block text-xs text-muted-foreground">
          {empty
            ? "no course registered from this brief yet"
            : `${courses.length} course${courses.length === 1 ? "" : "s"} · ${[...byFormat]
                .map(([format, count]) => `${count} × ${format}`)
                .join(" · ")}`}
        </span>
        {comparing && !empty ? (
          <span className="mt-1 flex flex-wrap gap-1">
            {arms.map((arm) => {
              const count = countFor(courses, arm.id);
              return (
                <Badge key={arm.key} variant={count === 0 ? "warning" : "secondary"}>
                  {arm.label}: {count}
                </Badge>
              );
            })}
          </span>
        ) : null}
      </span>
    </label>
  );
}

/** The warning that keeps an A/B from being unpaired without anyone noticing. Comparing
 *  versions is only meaningful over the same commissions — the GLOSSARY requires
 *  `CompareStudies` to pair sets by briefs — so a commission that answered one version and
 *  not another leaves the two columns measuring different work. */
function UnpairedCommissions({
  briefs,
  arms,
}: {
  briefs: { text: string; courses: Course[] }[];
  arms: Arm[];
}) {
  if (arms.length < 2) return null;
  const unpaired = briefs.filter(
    (brief) =>
      brief.courses.length > 0 && arms.some((arm) => countFor(brief.courses, arm.id) === 0),
  );
  if (unpaired.length === 0) return null;

  return (
    <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
      {unpaired.length} of these commissions produced courses for some versions and none for
      others, so those versions are not answering the same work. Comparing them is still
      legitimate — it is a comparison over fewer paired commissions, and the round will not
      say which ones. Registering the missing courses first is what makes the two columns
      subtractable.
    </p>
  );
}

/** ADR-0023 §7 applied where it can still be acted on: two versions whose courses leave a
 *  different number of criteria unassessed are measured over different denominators, so the
 *  difference between their values is not interpretable. It informs and never blocks, which
 *  is why a cross-format A/B is permitted at all (ADR-0044 §7). */
function ArmCoverage({
  arms,
  unreadableIn,
}: {
  arms: Arm[];
  unreadableIn: (format: string) => number | null;
}) {
  if (arms.length < 2) return null;

  const described = arms
    .filter((arm) => arm.formats.length > 0)
    .map((arm) => ({
      label: arm.label,
      // One entry per format the arm's courses are in — `null` while the matching loads,
      // so "we do not know yet" never renders as "none".
      unreadable: [...new Set(arm.formats.map((format) => unreadableIn(format)))],
    }));
  if (described.some((arm) => arm.unreadable.includes(null))) return null;

  const signature = (arm: (typeof described)[number]) =>
    [...arm.unreadable].sort((a, b) => Number(a) - Number(b)).join(",");
  if (new Set(described.map(signature)).size < 2) return null;

  return (
    <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
      These versions are not measured over the same criteria:{" "}
      {described
        .map((arm) => `${arm.label} leaves ${arm.unreadable.join("/")} unassessed per course`)
        .join(", ")}
      . Each value is still correct on its own, but the difference between them is not — they
      have different denominators. Kept, not refused: a generator that changed its output
      format is exactly the change worth measuring.
    </p>
  );
}

/** Kept, not hidden. Filtering these courses out would shrink the dataset in silence and
 *  the round would answer less than the reader thinks — so the number they need is said
 *  here instead, while they can still act on it (readiness informs, it never blocks). */
function PartialCoverage({
  formats,
  courses,
  unreadableIn,
}: {
  formats: string[];
  courses: { format: string }[];
  unreadableIn: (format: string) => number | null;
}) {
  const partial = formats
    .map((format) => ({ format, unreadable: unreadableIn(format) ?? 0 }))
    .filter((entry) => entry.unreadable > 0)
    .map((entry) => {
      const count = courses.filter((c) => c.format === entry.format).length;
      return `${count} course${count === 1 ? "" : "s"} in ${entry.format} (${entry.unreadable} criteria each)`;
    });

  if (partial.length === 0) return null;
  return (
    <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
      Kept, not hidden: {partial.join(", ")} will come back with those criteria left
      unassessed. That is legitimate and the report will say so — but the round answers less
      than the whole instrument asks.
    </p>
  );
}

// ------------------------------------------------------------------------- confirmation

/** The one point of no return in the flow, saying both of its consequences with numbers.
 *  No metaphor: what stops being editable, and what the run will spend. */
function ConfirmRound({
  open,
  onClose,
  name,
  instrumentId,
  assessor,
  courses,
  arms,
  pending,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  name: string;
  instrumentId: string;
  assessor: AssessorPackageResponse | undefined;
  courses: number;
  arms: Arm[];
  pending: boolean;
  onConfirm: () => void;
}) {
  const calls = assessor?.uses_llm ? courses * assessor.executes.length : 0;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={name ? `Start “${name}”?` : "Start this round?"}
      description="This does two things at once, and neither can be undone."
    >
      <ul className="space-y-2 text-sm">
        <li className="rounded border p-2">
          <span className="font-medium">These three stop being editable</span>
          <span className="mt-1 block text-xs text-muted-foreground">
            <code>{instrumentId}</code> · {assessor?.display_name ?? "the chosen judge"} · these{" "}
            {courses} course{courses === 1 ? "" : "s"} · {scopeSummary(arms)}
            {arms.length > 1 ? ` (${arms.map((a) => `${a.label}: ${a.courses}`).join(", ")})` : ""}.
            Changing any of them afterwards means a new study.
          </span>
        </li>
        <li className="rounded border p-2">
          <span className="font-medium">
            {courses} course{courses === 1 ? "" : "s"} evaluated now
            {calls > 0 ? ` — about ${calls} LLM calls, spent on the backend's key` : " — no LLM cost"}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            It reports as it goes and can be stopped at any time. What finished stays judged.
          </span>
        </li>
      </ul>
      <p className="mt-3 text-xs text-muted-foreground">
        Signing off the report is a separate act, later, and also final.
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={pending}>
          Cancel
        </Button>
        <Button onClick={onConfirm} disabled={pending}>
          {pending ? <Spinner /> : null} Save &amp; evaluate
        </Button>
      </div>
    </Dialog>
  );
}

// -------------------------------------------------------------------------------- pure

/** One registered course, as the form needs it: what it is written in, and what made it. */
type Course = { format: string; versionId: Uuid | null };

/** One generator version the round measures, with what the selected briefs brought for it.
 *  `id: null` is the unknown-generator group, which only `"all"` can reach. */
type Arm = { key: string; id: Uuid | null; label: string; courses: number; formats: string[] };

function countFor(courses: Course[], versionId: Uuid | null) {
  return courses.filter((course) => course.versionId === versionId).length;
}

/** What the round measures, as columns. A listed scope names its own; `"all"` can only be
 *  read off the dataset, because a version registered but absent from these briefs is not
 *  something this round measures — and saying otherwise would invent an empty column. */
function armsOf(
  scope: GeneratorScope | null,
  courses: Course[],
  versions: GeneratorVersionResponse[],
): Arm[] {
  const label = (id: Uuid | null) => {
    if (id === null) return "unknown generator";
    const version = versions.find((v) => v.generator_version_id === id);
    return version ? `${version.name} ${version.version}` : id.slice(0, 8);
  };
  const ids: (Uuid | null)[] = Array.isArray(scope)
    ? scope
    : scope === "all"
      ? [...new Set(courses.map((course) => course.versionId))]
      : [];

  return ids.map((id) => {
    const mine = courses.filter((course) => course.versionId === id);
    return {
      key: id ?? "unknown",
      id,
      label: label(id),
      courses: mine.length,
      formats: [...new Set(mine.map((course) => course.format))].sort(),
    };
  });
}

/** How the round reads in one clause, so the summary and the confirmation agree. */
function scopeSummary(arms: Arm[]) {
  if (arms.length === 0) return "no courses to measure";
  if (arms.length === 1) return `measuring ${arms[0].label}`;
  return `comparing ${arms.length} generator versions`;
}

function ratifiedFor(
  packages: AssessorPackageResponse[],
  instrumentVersionId: string,
): AssessorPackageResponse[] {
  if (!instrumentVersionId) return [];
  return packages.filter(
    (pkg) =>
      pkg.assessor_id !== null &&
      pkg.lineage_versions.some(
        (version) => version.instrument_version_id === instrumentVersionId && version.ratified,
      ),
  );
}

/** How many of the instrument's criteria have no datum to read in this format. `null` while
 *  the answer is still loading, so "we do not know yet" never renders as "none". */
function unreadableCount(matching: { criteria: { missingData: string[] }[] } | undefined) {
  if (!matching) return null;
  return matching.criteria.filter((criterion) => criterion.missingData.length > 0).length;
}

function missing(
  name: string,
  instrumentId: string,
  assessorId: string,
  scopeDeclared: boolean,
  courses: number,
) {
  const gaps: string[] = [];
  if (!name.trim()) gaps.push("a name");
  if (!instrumentId) gaps.push("an instrument");
  if (!assessorId) gaps.push("a judge");
  if (!scopeDeclared) gaps.push("which generator versions it measures");
  if (courses === 0) gaps.push("at least one course");
  return gaps;
}
