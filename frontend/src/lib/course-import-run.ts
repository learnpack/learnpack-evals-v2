/**
 * One import of a list of courses: the loop, and everything known about how it is going.
 *
 * A module, not component state, and that is the whole point. Registering a course fetches
 * and parses its package, so a file of forty takes minutes — long enough that the operator
 * will go and look at something else while it runs. Client-side navigation does not stop the
 * loop (nothing here is tied to a request the browser would abort), but it does unmount the
 * screen, and a batch whose progress lived in that screen would carry on registering with
 * nobody able to see what it had done. Held here, the page is only a window on it: leave,
 * come back, and the same run is still there, still moving.
 *
 * Why a loop at all, rather than one call that registers the file: ADR-0027 — a batch is a
 * loop over the same use case, not another path — and the reasoning ADR-0035 §5 already
 * spent on the twin case next door, where a whole-set call would be a multi-minute write
 * with no progress and no bounded failure.
 *
 * Reloading or closing the tab DOES end it, and nothing here tries to survive that. What was
 * registered is registered — each course is its own transaction, and the request in flight
 * commits on the server whether or not anyone is still listening — so the record of how far
 * it got is the course list itself, and running the same file again finishes the rest,
 * because an unchanged package is a reported no-op.
 */

import type { ApiError } from "@/lib/api/client";
import type { RegisterBySourceRequest, RegisterBySourceResponse, Uuid } from "@/lib/api/types";

/**
 * How one row ended, in the four words the CLI's own summary uses (`_register_sources` in
 * `app/cli.py`): two doors onto one act should report it the same way.
 */
export type RowStatus = "pending" | "created" | "unchanged" | "conflict" | "invalid";

export interface ImportRow {
  url: string;
  status: RowStatus;
  detail: string;
}

/** What a whole file declares about every course in it: one format, one course version, one
 *  generator, one provenance — the same thing the CLI declares once for a whole run. */
export type ImportDeclaration = Omit<RegisterBySourceRequest, "source_locator">;

export interface ImportRun {
  rows: ImportRow[];
  /** Rows already decided — `rows.length` is the total. */
  done: number;
  running: boolean;
  /** True once the loop has ended, however it ended. */
  ended: boolean;
  /** A stop has been asked for and the row in flight is still finishing. It is a state of
   *  its own because the wait is long enough to look like nothing happened. */
  stopping: boolean;
  stopped: boolean;
  /** What this lot was declared to be, and the file its URLs came from. They live here and
   *  not on the screen because they stop being form fields the moment the run starts: from
   *  then on they are facts about the batch, and the batch outlives the page that started
   *  it. `null` while there is no batch at all. */
  declaration: ImportDeclaration | null;
  fileName: string | null;
  /** Every course the lot touched, created or not: an already-registered course is as much
   *  part of the lot when the question is whether this lot came back readable. */
  contentIds: Uuid[];
  created: number;
  unchanged: number;
  failed: number;
}

const IDLE: ImportRun = {
  rows: [],
  done: 0,
  running: false,
  ended: false,
  stopping: false,
  stopped: false,
  declaration: null,
  fileName: null,
  contentIds: [],
  created: 0,
  unchanged: 0,
  failed: 0,
};

let current: ImportRun = IDLE;
let stopRequested = false;
const listeners = new Set<() => void>();

function publish(next: ImportRun): void {
  current = next;
  for (const listener of listeners) listener();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** A stable reference while nothing changes, which is what `useSyncExternalStore` needs. */
export function getSnapshot(): ImportRun {
  return current;
}

/** Nothing has run on the server, and nothing can. */
export function getServerSnapshot(): ImportRun {
  return IDLE;
}

/** Back to nothing — what choosing another file does. Refused mid-run, since the run would
 *  keep writing into a snapshot the screen had already forgotten. */
export function reset(): void {
  if (current.running) return;
  stopRequested = false;
  publish(IDLE);
}

/**
 * Stop after the row in flight — never during it. Aborting the request would not undo the
 * write: the endpoint is a synchronous handler on a thread pool, so hanging up on it leaves
 * a course registered and this screen saying it was not.
 */
export function stop(): void {
  // Idempotent: a second click has nothing new to ask for, and publishing again would only
  // redraw the same sentence.
  if (!current.running || current.stopping) return;
  stopRequested = true;
  publish({ ...current, stopping: true });
}

/** What a row says when the server refused it. */
function refusal(error: ApiError): string {
  const declared = error.data?.declaredGenerator as
    | { name?: string; version?: string }
    | undefined;
  if (declared?.name && declared.version) {
    return `${error.message} — register ${declared.name} ${declared.version}, then run the same file again.`;
  }
  return error.message;
}

export interface ImportRequest {
  urls: string[];
  /** Named so the batch can say where its courses came from once the file input is gone. */
  fileName: string;
  declaration: ImportDeclaration;
  register: (request: RegisterBySourceRequest) => Promise<RegisterBySourceResponse>;
  /** Said when the loop ends, wherever the operator happens to be by then — which is why it
   *  is handed in here rather than watched for on the page. */
  announce: (run: ImportRun) => void;
}

export async function start({
  urls,
  fileName,
  declaration,
  register,
  announce,
}: ImportRequest): Promise<void> {
  if (current.running) return;
  stopRequested = false;
  publish({
    ...IDLE,
    running: true,
    declaration,
    fileName,
    rows: urls.map((url) => ({ url, status: "pending", detail: "" })),
  });

  // Sequential on purpose, the same reason the disk importer gives: each created course is
  // profiled inside its own request, so firing them together would hide which one is slow
  // and multiply the load for nothing.
  for (const [index, url] of urls.entries()) {
    if (stopRequested) break;

    let status: RowStatus;
    let detail: string;
    let contentId: Uuid | null = null;
    try {
      const result = await register({ ...declaration, source_locator: url });
      status = result.created ? "created" : "unchanged";
      detail = result.created
        ? `${result.artifact_count} artifacts discovered`
        : "the same bytes were already registered";
      contentId = result.content.content_id;
    } catch (error) {
      const failure = error as ApiError;
      // Conflict and invalid are the CLI's two kinds of refusal, and they are worth keeping
      // apart: a conflict is two declarations disagreeing about a fact, which somebody has
      // to settle, and an invalid is a package this path could not read.
      status = failure.status === 409 ? "conflict" : "invalid";
      detail = refusal(failure);
    }

    publish({
      ...current,
      rows: current.rows.map((row, at) => (at === index ? { ...row, status, detail } : row)),
      done: current.done + 1,
      contentIds: contentId ? [...current.contentIds, contentId] : current.contentIds,
      created: current.created + (status === "created" ? 1 : 0),
      unchanged: current.unchanged + (status === "unchanged" ? 1 : 0),
      failed: current.failed + (status === "conflict" || status === "invalid" ? 1 : 0),
    });
  }

  publish({
    ...current,
    running: false,
    stopping: false,
    ended: true,
    // Stopped only if something was actually left unasked. Asking for a stop while the last
    // row is in flight stops nothing, and saying "the rest were never asked for" would name
    // a rest that never existed.
    stopped: stopRequested && current.done < urls.length,
  });
  stopRequested = false;
  announce(current);
}
