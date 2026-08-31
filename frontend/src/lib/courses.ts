/** How a course is written wherever somebody reads one (ADR-0059).
 *
 * Two functions rather than one, because the two readers are not the same reader.
 *
 * An **admin** is shown the name and, beside it, the `external_id` — the identity they type
 * into a command, paste into a CSV and match against a folder. Where a course declares no
 * name, the identifier is the label, which is what the console showed before there were
 * names at all.
 *
 * An **evaluator** is never shown the `external_id`: a LearnpackV1 slug can name the
 * generator outright and a LearnpackV2 id names a run, and the panel is blind to which
 * generator produced what (ADR-0052 §7). What is left when a course has no name is the
 * reference below — opaque, and enough to quote when something will not load.
 *
 * Plain string helpers rather than components, for the reason `assessor-label.tsx` gives:
 * half the callers need the text and not the markup — a `title` attribute, a search
 * predicate, a sort key.
 */

/** Anything the API hands over that names a course. Both spellings of the title, because
 *  the registry serves `title` on a content and Orchestration serves `content_title` on an
 *  assignment: one course, two payloads, and the caller should not have to care. */
interface Named {
  title?: string | null;
  content_title?: string | null;
  external_id?: string | null;
}

/** The first characters of an id — opaque, stable, and short enough to read out loud. */
export function courseRef(contentId: string): string {
  return contentId.slice(0, 8);
}

/** For the console: the name, else the identity, else the reference. */
export function courseLabel(course: Named | null | undefined, contentId?: string): string {
  const named = course?.title ?? course?.content_title;
  if (named) return named;
  if (course?.external_id) return course.external_id;
  return contentId ? `Course ${courseRef(contentId)}` : "Unknown course";
}

/** For the evaluator: the name, else the reference. Never the identity — see above. */
export function assignedCourseLabel(title: string | null, contentId: string): string {
  return title ?? `Course ${courseRef(contentId)}`;
}
