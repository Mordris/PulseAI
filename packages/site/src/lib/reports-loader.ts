import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { compile } from "@pulseai/contracts";
import type { Loader } from "astro/loaders";
import type { z } from "zod";
import { loadSiteContext, type SiteContext } from "./context.ts";
import { requireInstanceDir, sitePaths } from "./setup.ts";
import type { Report } from "./types.ts";

const REPORT_SCHEMA = "report.schema.json";
const ITEM_TYPE_SCHEMA_DIR = "item-types";
const REPORT_FILE = "report.json";
/** reports/YYYY/MM/DD/report.json, relative to the reports directory. */
const REPORT_PATH = /^(\d{4})[/\\](\d{2})[/\\](\d{2})[/\\]report\.json$/;

export class ReportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ReportError";
  }
}

function describeIssues(error: z.ZodError, file: string, prefix: string[] = []): string[] {
  return error.issues.map((issue) => {
    const path = [...prefix, ...issue.path.map(String)].join("/") || "<root>";
    return `${file}: ${path}: ${issue.message}`;
  });
}

/** Whether the runtime knows `name` as an IANA time zone (the masthead formats the window in it). */
function isTimeZone(name: string): boolean {
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: name });
    return true;
  } catch {
    return false;
  }
}

export type ReportValidator = (data: unknown, file: string) => Report;

/**
 * Validate reports with the context's schemas: the report schema, each item's detail schema, and
 * the registry references the frame needs to render (section and item type). The remaining
 * cross-reference rules belong to `pulse validate`, which runs before a report is published.
 */
export function createReportValidator(context: SiteContext): ReportValidator {
  const reportSchema = context.schemas[REPORT_SCHEMA];
  if (reportSchema === undefined) throw new ReportError(`the site context has no ${REPORT_SCHEMA}`);
  const report = compile(reportSchema);
  const sections = new Set(context.sections.map((section) => section.id));
  const details = new Map(
    context.item_types.map((itemType) => {
      const name = `${ITEM_TYPE_SCHEMA_DIR}/${itemType.schema}`;
      const schema = context.schemas[name];
      if (schema === undefined) throw new ReportError(`the site context has no ${name}`);
      return [itemType.id, compile(schema)] as const;
    }),
  );
  return (data, file) => {
    const parsed = report.safeParse(data);
    if (!parsed.success) throw new ReportError(describeIssues(parsed.error, file).join("\n"));
    const doc = data as Report;
    const problems: string[] = [];
    for (const key of ["items", "signals"] as const) {
      doc[key].forEach((item, index) => {
        const where = `${key}/${index}`;
        if (!sections.has(item.section)) {
          problems.push(`${file}: ${where}/section: unknown section "${item.section}"`);
        }
        const detail = details.get(item.type);
        if (detail === undefined) {
          problems.push(`${file}: ${where}/type: unknown item type "${item.type}"`);
          return;
        }
        const result = detail.safeParse(item.detail);
        if (!result.success)
          problems.push(...describeIssues(result.error, file, [where, "detail"]));
      });
    }
    if (!isTimeZone(doc.meta.window.tz)) {
      problems.push(`${file}: meta/window/tz: unknown time zone "${doc.meta.window.tz}"`);
    }
    for (const section of Object.keys(doc.section_notes)) {
      if (!sections.has(section)) {
        problems.push(`${file}: section_notes/${section}: unknown section "${section}"`);
      }
    }
    if (problems.length > 0) throw new ReportError(problems.join("\n"));
    return doc;
  };
}

export interface ReportFile {
  file: string;
  /** The date the path names, YYYY-MM-DD. */
  date: string;
}

/** Every report.json below dir, oldest first; one in the wrong place is an error. */
export function reportFiles(dir: string): ReportFile[] {
  let entries: string[];
  try {
    entries = readdirSync(dir, { recursive: true, encoding: "utf8" });
  } catch {
    return [];
  }
  const files: ReportFile[] = [];
  for (const rel of entries) {
    if (!rel.endsWith(REPORT_FILE)) continue;
    const match = REPORT_PATH.exec(rel);
    if (match === null) {
      throw new ReportError(`${join(dir, rel)}: reports live at reports/YYYY/MM/DD/report.json`);
    }
    files.push({ file: join(dir, rel), date: `${match[1]}-${match[2]}-${match[3]}` });
  }
  return files.sort((a, b) => a.date.localeCompare(b.date));
}

export function readReport(entry: ReportFile, validate: ReportValidator): Report {
  let data: unknown;
  try {
    data = JSON.parse(readFileSync(entry.file, "utf8"));
  } catch (error) {
    throw new ReportError(`${entry.file}: ${(error as Error).message}`);
  }
  const report = validate(data, entry.file);
  if (report.meta.date !== entry.date) {
    throw new ReportError(
      `${entry.file}: meta.date is ${report.meta.date}, but the file is filed under ${entry.date}`,
    );
  }
  return report;
}

/** The content loader: every report of the instance, validated, keyed by date. */
export function reportsLoader(): Loader {
  return {
    name: "pulse-reports",
    async load({ store, logger, generateDigest }) {
      const paths = sitePaths(requireInstanceDir());
      const validate = createReportValidator(loadSiteContext(paths.contextFile));
      store.clear();
      const files = reportFiles(paths.reportsDir);
      for (const entry of files) {
        const report = readReport(entry, validate);
        const data = report as unknown as Record<string, unknown>;
        store.set({ id: entry.date, data, digest: generateDigest(data) });
      }
      logger.info(`loaded ${files.length} reports from ${paths.reportsDir}`);
    },
  };
}
