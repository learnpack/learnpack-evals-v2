/** Handing a table to the person who has to analyse it elsewhere.
 *
 *  The console has no other download, and this one exists for a narrow reason: a campaign's
 *  raw answers are the input of analyses the report cannot anticipate — a correlation, a
 *  severity model, a chart somebody wants in a paper. Without it, every such question becomes
 *  a feature request against this screen.
 *
 *  RFC 4180 quoting, which is the whole of the format: quote every field, double the quotes
 *  inside it. A CRLF line ending because Excel still wants one, and a UTF-8 BOM because
 *  without it Excel reads accented names as mojibake — the two concessions that decide
 *  whether the file opens correctly for the person who asked for it.
 */

function field(value: string | number): string {
  return `"${String(value).replaceAll('"', '""')}"`;
}

export function toCsv(columns: string[], rows: (string | number)[][]): string {
  return [columns, ...rows].map((row) => row.map(field).join(",")).join("\r\n");
}

/** Save text as a file in the reader's browser. Nothing leaves the page. */
export function downloadCsv(filename: string, csv: string): void {
  const url = URL.createObjectURL(
    new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // The object URL pins the blob in memory until it is released, and nothing else will.
  URL.revokeObjectURL(url);
}

/** A filename that stays sortable and does not depend on what somebody typed as a name. */
export function csvFilename(prefix: string, label: string): string {
  const slug =
    label
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "untitled";
  return `${prefix}-${slug}-${new Date().toISOString().slice(0, 10)}.csv`;
}
