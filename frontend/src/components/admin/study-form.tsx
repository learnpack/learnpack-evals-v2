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
  useInstruments,
  useMatchings,
  useOpenStudy,
  useStartRound,
  useUpdateStudyDraft,
} from "@/lib/api/hooks";
import type { AssessorPackageResponse, StudyResponse, Uuid } from "@/lib/api/types";

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

  const declare = useDeclareStudy();
  const update = useUpdateStudyDraft();
  const openStudy = useOpenStudy();
  const startRound = useStartRound();

  const [name, setName] = useState(study?.name ?? "");
  const [description, setDescription] = useState(study?.description ?? "");
  const [instrumentId, setInstrumentId] = useState(study?.instrument_version_id ?? "");
  const [assessorId, setAssessorId] = useState<string>(study?.assessor_id ?? "");
  const [briefIds, setBriefIds] = useState<Uuid[]>(study?.brief_ids ?? []);
  const [confirming, setConfirming] = useState(false);

  const published = (instruments.data ?? []).filter((i) => i.status === "published");
  const eligible = ratifiedFor(packages.data ?? [], instrumentId);
  const chosenAssessor = (packages.data ?? []).find((pkg) => pkg.assessor_id === assessorId);

  // Courses per brief, from what is registered. The recipe selects briefs; the dataset the
  // backend materializes is exactly this, so the count on screen is the count that will run.
  const coursesByBrief = useMemo(() => {
    const grouped = new Map<Uuid, { format: string }[]>();
    for (const content of contents.data ?? []) {
      if (content.brief_id === null) continue;
      grouped.set(content.brief_id, [
        ...(grouped.get(content.brief_id) ?? []),
        { format: content.package_format },
      ]);
    }
    return grouped;
  }, [contents.data]);

  const selectedCourses = briefIds.flatMap((id) => coursesByBrief.get(id) ?? []);
  const formats = [...new Set(selectedCourses.map((c) => c.format))].sort();
  const matchings = useMatchings(instrumentId || null, formats);

  const complete = Boolean(name.trim() && instrumentId && assessorId && selectedCourses.length);
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
          id="study-courses"
          label="Courses"
          hint="Picked by brief — each brief brings the courses registered from it."
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
                    checked={briefIds.includes(brief.brief_id)}
                    unreadableIn={(format) => unreadableCount(matchings.byFormat.get(format))}
                    onToggle={() => toggleBrief(brief.brief_id)}
                  />
                );
              })
            )}
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
              ? `${selectedCourses.length} course${selectedCourses.length === 1 ? "" : "s"} · judged by ${chosenAssessor?.display_name ?? assessorId} · against ${instrumentId}`
              : `Still missing ${missing(name, instrumentId, assessorId, selectedCourses.length).join(", ")}.`}
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

function BriefRow({
  text,
  courses,
  checked,
  unreadableIn,
  onToggle,
}: {
  text: string;
  courses: { format: string }[];
  checked: boolean;
  unreadableIn: (format: string) => number | null;
  onToggle: () => void;
}) {
  const byFormat = new Map<string, number>();
  for (const course of courses) byFormat.set(course.format, (byFormat.get(course.format) ?? 0) + 1);
  const empty = courses.length === 0;

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
      </span>
    </label>
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
  pending,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  name: string;
  instrumentId: string;
  assessor: AssessorPackageResponse | undefined;
  courses: number;
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
            {courses} course{courses === 1 ? "" : "s"}. Changing any of them afterwards means a
            new study.
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

function missing(name: string, instrumentId: string, assessorId: string, courses: number) {
  const gaps: string[] = [];
  if (!name.trim()) gaps.push("a name");
  if (!instrumentId) gaps.push("an instrument");
  if (!assessorId) gaps.push("a judge");
  if (courses === 0) gaps.push("at least one course");
  return gaps;
}
