/**
 * What an evaluator is told before they start, in one place because it is said twice: on the
 * list, where they arrive, and beside the form, where two of these five stop being advice and
 * start being needed.
 *
 * The order is not decorative. Rules 2 and 3 exist because the instrument reads the whole
 * course — several statements are about how it builds across lessons, so skipping lessons
 * takes their evidence away, while the exercises only have to be *read*: what they ask the
 * learner to do is what two of the items judge. Rule 4 is the one that protects the
 * measurement: ADR-0052 §4 makes the bottom of the scale an answer ("the course does not do
 * this") and the abstention a different act stored as a null score, so a rater who abstains
 * where they should have disagreed decorrelates the two sides on the courses carrying the most
 * information.
 *
 * Two constraints on any edit to this copy:
 *
 * - **It names no generator, no version and no AI.** The panel is blind to what produced a
 *   course, and to whether anything produced it (ADR-0053, ADR-0057 §3).
 * - **It never says "not applicable".** ADR-0052 §4 avoids that reading on purpose: it is the
 *   wording that collects an absence — which belongs at the bottom of the scale — under the
 *   abstention instead.
 */
export function HowThisWorks() {
  return (
    <ol className="list-decimal space-y-1.5 pl-4 text-xs text-muted-foreground">
      <li>
        {/* No count: a course that declares less is asked fewer of them (ADR-0053), so a
            number here would be wrong on the very courses it would be read on. */}
        <span className="font-medium text-foreground">
          Read the form&apos;s statements first.
        </span>{" "}
        They tell you what to watch for as you go through the course.
      </li>
      <li>
        <span className="font-medium text-foreground">See all the lessons, in order.</span>{" "}
        Statements about the course&apos;s coherence, continuity and progression can only be
        answered across lessons.
      </li>
      <li>
        <span className="font-medium text-foreground">
          Completing the exercises isn&apos;t required.
        </span>{" "}
        They appear inside the lessons — reading what each one asks for is enough.
      </li>
      <li>
        <span className="font-medium text-foreground">
          &quot;Strongly disagree&quot; is an answer.
        </span>{" "}
        If the course simply doesn&apos;t do what a statement describes, say so. Use
        &quot;I couldn&apos;t see enough&quot; only when you genuinely couldn&apos;t tell.
      </li>
      <li>
        {/* Open on purpose: tying it to disagreement would collect only half of what an
            expert notices, and the instrument cannot ask about what it does not know to
            ask. Agreeing with a caveat is worth as much as disagreeing. */}
        <span className="font-medium text-foreground">Add a comment on any item</span> where the
        scale alone doesn&apos;t capture what you saw.
      </li>
    </ol>
  );
}
