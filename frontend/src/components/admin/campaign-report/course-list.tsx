"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { rankContents } from "@/components/admin/campaign-report/ranking";
import { courseLabel } from "@/lib/courses";
import { cn } from "@/lib/utils";
import type {
  CampaignReport,
  CampaignReportContent,
  CampaignReportItem,
  IndividualEvaluation,
} from "@/lib/api/types";

/** The courses, most contested first — and, inside one, what each expert actually said.
 *
 *  The per-expert answers and their comments have been in this payload's shape since slice 1
 *  and were never rendered: the console downloaded them on every request and dropped them.
 *  They are the whole reason to convene a panel — a number says two people differed, a
 *  comment says why — so opening a course is where the report stops summarising.
 */
export function CourseList({ report }: { report: CampaignReport }) {
  const rows = rankContents(report);

  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium">Courses</h3>
        <p className="text-xs text-muted-foreground">
          Ordered by how far apart the panel was, not alphabetically. Open one to read the
          experts side by side.
        </p>
      </div>
      <ul className="divide-y">
        {rows.map((content) => (
          <CourseEntry key={content.content_id} content={content} items={report.items} />
        ))}
      </ul>
    </section>
  );
}

function CourseEntry({
  content,
  items,
}: {
  content: CampaignReportContent;
  items: CampaignReportItem[];
}) {
  const [open, setOpen] = useState(false);
  const counted = content.evaluations.filter((e) => !e.superseded);

  return (
    <li className="text-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 px-4 py-3 text-left hover:bg-accent/40"
      >
        <ChevronDown
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        <span className="min-w-0 flex-1 space-y-1">
          <span className="block font-medium">{courseLabel(content, content.content_id)}</span>
          <span className="block text-xs text-muted-foreground">
            {content.external_id} · {content.submitted_count}/{content.required} submitted
            {content.disagreement.max_abs_diff !== null
              ? ` · ${content.disagreement.contested_items} items contested, widest gap ${content.disagreement.max_abs_diff}`
              : " · nothing to compare yet"}
          </span>
        </span>
        <span className="hidden shrink-0 items-center gap-1 sm:flex">
          {content.completed ? (
            <Badge variant="success">complete</Badge>
          ) : (
            <Badge variant="outline">in progress</Badge>
          )}
        </span>
      </button>

      {open ? (
        <div className="border-t bg-muted/20 px-4 py-3">
          {counted.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nobody has submitted this one yet.</p>
          ) : (
            <SideBySide items={items} evaluations={content.evaluations} />
          )}
        </div>
      ) : null}
    </li>
  );
}

/** One row per item, one column per expert — the layout the comparison is actually about.
 *
 *  Superseded evaluations get a column too, marked: what somebody first answered and then
 *  corrected is part of the record, and hiding it would make a correction indistinguishable
 *  from a first answer.
 */
function SideBySide({
  items,
  evaluations,
}: {
  items: CampaignReportItem[];
  evaluations: IndividualEvaluation[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <thead>
          <tr className="text-left align-bottom">
            <th className="w-1/2 pb-2 pr-3 font-medium">Item</th>
            {evaluations.map((evaluation) => (
              <th key={evaluation.evaluation_id} className="pb-2 pr-3 font-medium">
                <span className="block">
                  {evaluation.assessor_name ?? evaluation.assessor_id.slice(0, 8)}
                </span>
                {evaluation.superseded ? (
                  <span className="block text-xs font-normal text-muted-foreground">
                    superseded
                  </span>
                ) : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((item) => (
            <tr key={item.criterion_id} className="align-top">
              <td className="py-2 pr-3" title={item.criterion_id}>
                {item.prompt}
              </td>
              {evaluations.map((evaluation) => {
                const answer = evaluation.scores.find(
                  (s) => s.criterion_id === item.criterion_id,
                );
                return (
                  <td key={evaluation.evaluation_id} className="py-2 pr-3">
                    <Answer
                      score={answer?.score ?? null}
                      derived={answer?.derived ?? false}
                      comment={answer?.comment ?? null}
                      missing={answer === undefined}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The three empties, told apart on the screen as they are in the data (ADR-0060 §4). */
function Answer({
  score,
  derived,
  comment,
  missing,
}: {
  score: number | null;
  derived: boolean;
  comment: string | null;
  missing: boolean;
}) {
  if (missing) return <span className="text-xs text-muted-foreground">—</span>;
  return (
    <span className="space-y-1">
      {derived ? (
        <span className="block text-xs italic text-muted-foreground" title="the course declares nothing this item is about (ADR-0053)">
          not asked{score !== null ? ` · derived ${score}` : ""}
        </span>
      ) : score === null ? (
        <span className="block text-xs italic text-muted-foreground" title="the expert looked and could not judge it">
          could not judge
        </span>
      ) : (
        <span className="block font-semibold tabular-nums">{score}</span>
      )}
      {comment ? (
        <span className="block text-xs text-muted-foreground">“{comment}”</span>
      ) : null}
    </span>
  );
}
