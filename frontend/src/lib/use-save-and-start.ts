"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import type { ApiError } from "@/lib/api/client";
import {
  useDeclareStudy,
  useOpenStudy,
  useStartRound,
  useUpdateStudyDraft,
} from "@/lib/api/hooks";
import type { GeneratorScope, StudyResponse, Uuid } from "@/lib/api/types";

/** What a study draft is saved with. `generator_scope` is omitted while undeclared: absent
 *  leaves it alone, and `null` would be refused — there is no way to say "un-declare". */
export interface StudyDraftBody {
  name: string;
  description: string | null;
  instrument_version_id?: string;
  assessor_id: Uuid | null;
  brief_ids: Uuid[];
  generator_scope?: GeneratorScope;
}

/**
 * Saving a study, and saving, opening and evaluating it: the acts every screen that builds a
 * study ends with. The study form and the measuring wizard both call these, so there is one
 * sequence of requests and one set of messages for what can go wrong between them.
 *
 * `study` is the draft being edited, or nothing for one that does not exist yet.
 */
export function useSaveAndStart(study?: StudyResponse) {
  const router = useRouter();
  const declare = useDeclareStudy();
  const update = useUpdateStudyDraft();
  const openStudy = useOpenStudy();
  const startRound = useStartRound();

  /** Create or update, and answer with the study either way — the two differ in one verb. */
  async function save(body: StudyDraftBody): Promise<StudyResponse | null> {
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

  async function saveDraft(body: StudyDraftBody) {
    const saved = await save(body);
    if (!saved) return;
    toast.success("Draft saved.", { description: "Nothing is fixed yet — come back any time." });
    if (!study) router.push(`/admin/studies/${saved.study_id}`);
  }

  /** Save, open, evaluate — three requests on purpose. A failure in the middle leaves a
   *  valid draft, which is the state this whole redesign exists to make safe; a compound
   *  endpoint would trade that away for one round trip.
   *
   *  `onSettled` runs once the sequence has stopped, wherever it stopped, so a caller can
   *  close its confirmation. */
  async function saveAndEvaluate(body: StudyDraftBody, onSettled?: () => void) {
    const saved = await save(body);
    if (!saved) return;
    try {
      await openStudy.mutateAsync({ studyId: saved.study_id });
    } catch (err) {
      onSettled?.();
      toast.error("Saved, but the study did not start.", {
        description: (err as ApiError).message,
      });
      if (!study) router.push(`/admin/studies/${saved.study_id}`);
      return;
    }
    try {
      await startRound.mutateAsync({ studyId: saved.study_id, body: { re_evaluate: false } });
      toast.success("Evaluating", { description: "It reports as it goes, and can be stopped." });
    } catch (err) {
      toast.error("The study is open, but the batch did not start.", {
        description: (err as ApiError).message,
      });
    }
    onSettled?.();
    router.push(`/admin/studies/${saved.study_id}`);
  }

  return {
    save,
    saveDraft,
    saveAndEvaluate,
    saving: declare.isPending || update.isPending,
    busy: declare.isPending || update.isPending || openStudy.isPending || startRound.isPending,
  };
}
