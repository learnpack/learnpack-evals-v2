"use client";

import { EmptyState } from "@/components/ui/states";
import { MeasureWizard } from "@/components/admin/measure-wizard";
import { IS_LOCAL_AUTH } from "@/lib/auth";

/** Measuring a batch, as a guided flow (ADR-0070). The view with every option is
 *  `/admin/measure/all`. */
export default function EvaluateCoursesPage() {
  // A build-time constant, so the whole flow drops out of a production bundle. Reaching it
  // there anyway would only find 404s: the scan endpoints exist only on a local setup.
  if (!IS_LOCAL_AUTH) {
    return (
      <div className="max-w-3xl">
        <EmptyState
          title="Importing from a folder works only on a local setup"
          hint="It reads folders on the machine running the API. In a deployed console the same job is two screens: Courses → Add course, then Studies → New study."
        />
      </div>
    );
  }
  return <MeasureWizard />;
}
