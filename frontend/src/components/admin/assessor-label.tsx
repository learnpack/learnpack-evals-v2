/** Anything that names an assessor. Two spellings of the id because the two payloads spell
 *  it differently and always did: what a report freezes is camelCase (it is a document),
 *  what the HTTP API serves is snake_case (it is a response model). One label helper across
 *  both beats one per convention. */
interface Nameable {
  name: string | null;
  version: string | null;
  assessorId?: string;
  assessor_id?: string;
}

/** How an assessor is written wherever a judgment's author is shown (ADR-0042).
 *
 *  `name:version` is the identity a person recognises and the only form that means anything
 *  outside the store that minted the row — but it belongs to an automated artifact, and a
 *  human assessor has neither half. So the id is the fallback rather than an empty span: a
 *  judgment whose author cannot be labelled still has one, and saying nothing would be the
 *  exact silence this whole change ended.
 *
 *  A plain string helper beside the component because half the callers need the text and not
 *  the markup — a badge inside a sentence, a `title`, a sort key. */
export function assessorLabel(assessor: Nameable | null | undefined): string {
  if (!assessor) return "unknown assessor";
  if (assessor.name && assessor.version) return `${assessor.name}:${assessor.version}`;
  return assessor.assessorId ?? assessor.assessor_id ?? "unknown assessor";
}

export function AssessorLabel({ assessor }: { assessor: Nameable | null | undefined }) {
  return <code className="text-xs">{assessorLabel(assessor)}</code>;
}
