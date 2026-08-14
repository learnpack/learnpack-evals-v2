/** Turning an adapter's locator into a sentence.
 *
 * A locator says where in a package a datum came from, and the executors pass the profile
 * entry's own locator straight through to the criterion outcome — so the shapes reaching a
 * report are exactly the shapes the profile viewer already decodes. Rendered raw it is
 * JSON; rendered through this it is usually the whole answer a reader wanted, which is why
 * it belongs above a quote rather than beside it.
 *
 * Unknown shapes fall through to the JSON rather than to "unknown": a shape nobody has
 * taught this function about is still evidence, and hiding it would be the worse failure.
 */
export function describeLocator(locator: Record<string, unknown> | null): string {
  if (!locator) return "unknown source";
  const {
    source,
    key,
    kind,
    kinds,
    locator: path,
    path: jsonPath,
  } = locator as {
    source?: string;
    key?: string;
    kind?: string;
    kinds?: string[];
    locator?: string;
    path?: string;
  };
  if (source === "metadata" && key) return `declared metadata · ${key}`;
  if (source === "artifact" && kind) {
    return `artifact ${kind} · ${path ?? ""}${jsonPath ? ` · ${jsonPath}` : ""}`;
  }
  if (source === "artifacts" && kinds) return `artifacts · ${kinds.join(", ")}`;
  return JSON.stringify(locator);
}
