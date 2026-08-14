"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StudyForm } from "@/components/admin/study-form";

/** Creating a study is filling in the form once. The same form serves a draft that already
 *  has an id — see the study's own page — because they were never two screens. */
export default function NewStudyPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link
          href="/admin/studies"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Studies
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New study</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          A study is one round: an instrument, a judge and a set of courses. Everything here
          can change until the round starts.
        </p>
      </div>

      <StudyForm />
    </div>
  );
}
