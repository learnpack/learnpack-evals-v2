"use client";

import { useMemo, useState } from "react";
import { FileText } from "lucide-react";
import { LoadingState } from "@/components/ui/states";
import { assessorLabel } from "@/components/admin/assessor-label";
import { CaveatsLine } from "@/components/admin/study-report/caveats-line";
import { ClaimValiditySection } from "@/components/admin/study-report/claim-validity";
import { CourseList } from "@/components/admin/study-report/course-list";
import { CriteriaRollup } from "@/components/admin/study-report/criteria-rollup";
import { DocumentBand } from "@/components/admin/study-report/document-band";
import { WeakestClaims } from "@/components/admin/study-report/weakest-claims";
import {
  useClaimValidity,
  useInstruments,
  useStudyCriterionOutcomes,
  useStudyReport,
  useStudyReportPreview,
} from "@/lib/api/hooks";
import type {
  ClaimValidity,
  DocumentSource,
  ReportBody,
  StudyResponse,
  Uuid,
} from "@/lib/api/types";

/** The study's result, readable before it is signed.
 *
 *  One renderer, two sources. While the study is not signed off this shows the preview —
 *  what signing off would write, composed from today's judgments — and once it is, the
 *  frozen document. Only `DocumentBand` knows which; everything below it receives
 *  `ReportBody`, the shape the two payloads have in common, and could not tell them apart
 *  if it tried.
 *
 *  The human text every layer reads (claim statements, criterion statements, pass
 *  conditions, failure modes) is joined from the instrument rather than duplicated into the
 *  frozen document: the version is immutable, so the join is stable, and the report stays
 *  the size it is. */
export function StudyReportSection({ study }: { study: StudyResponse }) {
  const signedOff = study.status === "signed_off";
  const frozen = useStudyReport(study.study_id, signedOff);
  const preview = useStudyReportPreview(study.study_id);
  const outcomes = useStudyCriterionOutcomes(study.study_id);
  const instruments = useInstruments();

  // The reader's choice of campaign lives here because two things answer to it: the validity
  // table below, and the badge each claim carries above it (ADR-0063 §7).
  const [campaign, setCampaign] = useState<Uuid | "">("");
  const validity = useClaimValidity(
    campaign || null,
    study.assessor_id,
    study.instrument_version_id,
  );
  const validityByClaim = useMemo(
    () => new Map<string, ClaimValidity>((validity.data?.claims ?? []).map((c) => [c.claim_id, c])),
    [validity.data],
  );

  const instrument = (instruments.data ?? []).find(
    (candidate) => candidate.instrument_version_id === study.instrument_version_id,
  );

  // The frozen document is the record once it exists; the preview stands in until then.
  const body: ReportBody | undefined = signedOff ? frozen.data?.report : preview.data;
  const source = documentSource(signedOff, frozen.data?.report, preview.data);

  if (!body || !source) return <LoadingState label="Composing the report…" />;

  const externalIdOf = (contentId: string) =>
    body.contents.find((content) => content.contentId === contentId)?.externalId ?? contentId;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-lg font-semibold tracking-tight">What this round found</h2>
        <span className="text-xs text-muted-foreground">
          {body.instrumentVersionId ?? "no instrument pinned"} · dataset of{" "}
          {body.dataset.size} · {Object.keys(body.judgmentIdsUsed).length} judgments
          {/* Who judged, beside what they judged against. Absent on reports frozen before
              ADR-0042, which are read as the records they are rather than annotated with a
              guess. */}
          {body.assessorsUsed?.length
            ? ` · judged by ${body.assessorsUsed.map(assessorLabel).join(", ")}`
            : ""}
        </span>
      </div>

      <DocumentBand source={source} />
      <WeakestClaims body={body} validity={validityByClaim} />
      {outcomes.data ? (
        <CriteriaRollup
          outcomes={outcomes.data}
          instrument={instrument}
          externalIdOf={externalIdOf}
        />
      ) : null}
      <CourseList body={body} outcomes={outcomes.data} instrument={instrument} />
      <ClaimValiditySection
        campaign={campaign}
        onCampaignChange={setCampaign}
        validity={validity}
        pinned={Boolean(study.assessor_id && study.instrument_version_id)}
      />
      <CaveatsLine body={body} />
    </div>
  );
}

/** Which of the three things the reader is holding.
 *
 *  `recomposed` is the case the obvious two miss: a preview of an already signed-off study
 *  is the same composition making a different claim about itself, and the band must not
 *  offer it as the record. */
function documentSource(
  signedOff: boolean,
  frozen: { signedOffAt: string; signedOffBy: string | null } | undefined,
  preview: { composedAt: string; gaps: { gap: string }[]; frozenRecord: { note: string } } | undefined,
): DocumentSource | null {
  if (signedOff && frozen) {
    return { kind: "frozen", signedOffAt: frozen.signedOffAt, signedOffBy: frozen.signedOffBy };
  }
  if (!preview) return null;
  if (signedOff) {
    return {
      kind: "recomposed",
      composedAt: preview.composedAt,
      gaps: preview.gaps,
      note: preview.frozenRecord.note,
    };
  }
  return { kind: "preview", composedAt: preview.composedAt, gaps: preview.gaps };
}
