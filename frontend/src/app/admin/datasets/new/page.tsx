"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { DatasetForm } from "@/components/admin/dataset-form";

export default function NewDatasetPage() {
  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <Link
          href="/admin/datasets"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> All datasets
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New dataset</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Name the set and pick its courses. Declaring it freezes its first version.
        </p>
      </div>

      <DatasetForm />
    </div>
  );
}
