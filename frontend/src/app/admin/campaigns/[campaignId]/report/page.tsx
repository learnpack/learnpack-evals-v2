"use client";

import { use, useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { Caveats } from "@/components/admin/campaign-report/caveats";
import { CollectionBand } from "@/components/admin/campaign-report/collection-band";
import { CourseList } from "@/components/admin/campaign-report/course-list";
import { DimensionProfile } from "@/components/admin/campaign-report/dimension-profile";
import { ItemAgreement } from "@/components/admin/campaign-report/item-agreement";
import { ANSWER_COLUMNS, answerRows } from "@/components/admin/campaign-report/ranking";
import { Verdict } from "@/components/admin/campaign-report/verdict";
import { useCampaignReport, useDatasets, useGoldenStatus } from "@/lib/api/hooks";
import { csvFilename, downloadCsv, toCsv } from "@/lib/csv";

/** One campaign's result (ADR-0060).
 *
 *  Reading order is the argument: what the round has collected, then which items the experts
 *  read the same way, then what they said, then the courses, then what none of it covers.
 *  Agreement comes before the scores because with two experts per course it is the number
 *  that decides whether the scores mean anything.
 */
export default function CampaignReportPage({
  params,
}: {
  params: Promise<{ campaignId: string }>;
}) {
  const { campaignId } = use(params);
  const report = useCampaignReport(campaignId);
  const golden = useGoldenStatus(campaignId);
  const datasets = useDatasets();

  /** Where the scope came from (ADR-0058 §5). Null on campaigns opened before sets were
   *  named — they were typed into a form, and the line says so rather than guessing. */
  const scopeOrigin = useMemo(() => {
    const versionId = report.data?.dataset_version_id;
    if (!versionId) return null;
    for (const dataset of datasets.data ?? []) {
      const version = dataset.versions.find((v) => v.version_id === versionId);
      if (version) return { dataset, version };
    }
    return null;
  }, [report.data, datasets.data]);

  if (report.isLoading) return <LoadingState label="Composing the report…" />;
  if (report.error) return <ErrorState message={(report.error as Error).message} />;
  if (!report.data) return <ErrorState message="Campaign not found." />;

  const data = report.data;

  return (
    <div className="max-w-5xl">
      <Link
        href={`/admin/campaigns/${campaignId}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Back to the campaign
      </Link>

      <div className="mb-6">
        <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold tracking-tight">
          {data.name}
          <Badge variant={data.status === "open" ? "success" : "secondary"}>{data.status}</Badge>
        </h1>
        {data.description ? (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{data.description}</p>
        ) : null}
        {/* Provenance, in one line: what was asked, of what, by how many. Everything a reader
            needs to say where a number came from without opening another screen. */}
        <p className="mt-1 text-sm text-muted-foreground">
          {data.instrument.name} · {data.instrument.version} · quorum{" "}
          {data.quorum.required_per_content} ·{" "}
          {scopeOrigin ? (
            <>
              {data.quorum.contents_in_scope} courses from{" "}
              <Link
                href={`/admin/datasets/${scopeOrigin.dataset.dataset_id}`}
                className="underline"
              >
                {scopeOrigin.dataset.name}
              </Link>{" "}
              v{scopeOrigin.version.ordinal}
            </>
          ) : (
            `${data.quorum.contents_in_scope} courses, chosen before sets were named`
          )}
        </p>
      </div>

      <div className="space-y-6">
        <CollectionBand report={data} />
        <Verdict report={data} golden={golden.data} />
        <ItemAgreement report={data} />

        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">What the panel said</h2>
            <p className="text-xs text-muted-foreground">
              Grouped by dimension, as the instrument groups it — read together, never added
              together. The distribution is beside the mean because on a five-point scale they
              are not the same information.
            </p>
          </div>
          <DimensionProfile report={data} />
        </div>

        <CourseList report={data} />
        <Caveats report={data} />

        <div className="rounded-lg border bg-card px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Every answer, as a table</p>
              <p className="text-xs text-muted-foreground">
                One row per course, expert and item — corrections included and flagged. For the
                analyses this screen does not anticipate.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() =>
                downloadCsv(
                  csvFilename("campaign", data.name),
                  toCsv(ANSWER_COLUMNS, answerRows(data)),
                )
              }
            >
              <Download className="h-4 w-4" /> Download CSV
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
