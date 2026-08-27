/**
 * The course URLs a file names: the FIRST column of each row, and nothing else.
 *
 * The same reading the CLI does at the other door (`_read_source_list` in `app/cli.py`), and
 * deliberately the same one — two ways into one act that forgave different things would be
 * two acts. Forgiving about everything that is not the URL, because what arrives is a
 * spreadsheet somebody exported: a header row, the course name and a note in the columns
 * beside it, a blank line at the end, a `#` where someone parked a course they decided not
 * to measure. None of that changes which courses are meant, so none of it is an error.
 *
 * What is refused is what would register the wrong thing: an entry that is not an http(s)
 * URL — a course on disk is the CLI's business, since only the machine running the API can
 * read it — and a file that names no course at all. A non-URL is tolerated in exactly one
 * place, the first row, because that is where a spreadsheet writes its header; anywhere else
 * it is a row somebody meant to register.
 */

/** The file names no courses this page could register. */
export class UnusableCourseList extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnusableCourseList";
  }
}

export interface CourseList {
  /** In the order the file names them, each one once. */
  urls: string[];
  duplicatesIgnored: number;
  headerSkipped: boolean;
}

/**
 * The first field of a CSV row, honouring the quotes Excel puts around a field that holds a
 * comma. One row per line: a quoted field spanning newlines is not read, and its
 * continuation lands in the refusal below rather than being registered as something else.
 */
function firstColumn(row: string): string {
  const trimmed = row.trim();
  if (!trimmed.startsWith('"')) {
    const comma = trimmed.indexOf(",");
    return (comma === -1 ? trimmed : trimmed.slice(0, comma)).trim();
  }

  let field = "";
  let at = 1;
  while (at < trimmed.length) {
    if (trimmed[at] === '"') {
      // Two quotes inside a quoted field are one literal quote; a single one closes it.
      if (trimmed[at + 1] !== '"') break;
      field += '"';
      at += 2;
      continue;
    }
    field += trimmed[at];
    at += 1;
  }
  return field.trim();
}

export function readCourseList(text: string): CourseList {
  // Excel writes a BOM, and a BOM glued to the first URL is a fetch that fails for a reason
  // nobody could read off the error.
  const entries = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map(firstColumn)
    .filter((entry) => entry !== "" && !entry.startsWith("#"));

  const urls: string[] = [];
  let headerSkipped = false;
  entries.forEach((entry, index) => {
    if (entry.startsWith("http://") || entry.startsWith("https://")) {
      urls.push(entry);
    } else if (index === 0) {
      headerSkipped = true;
    } else {
      throw new UnusableCourseList(
        `'${entry}' is not an http(s) URL. Every row has to name a deployed course; a ` +
          `course that only exists on disk is registered from the terminal.`,
      );
    }
  });

  const unique = [...new Set(urls)];
  if (unique.length === 0) {
    throw new UnusableCourseList("This file names no course URLs.");
  }
  return {
    urls: unique,
    duplicatesIgnored: urls.length - unique.length,
    headerSkipped,
  };
}
