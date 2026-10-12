import { getCollection } from "astro:content";
import type { Report } from "./types.ts";

/** Every report of the instance, newest first. */
export async function allReports(): Promise<Report[]> {
  // Typed by hand so this also type-checks before `astro sync` has generated content types.
  const entries: { data: unknown }[] = await getCollection("reports");
  return entries
    .map((entry) => entry.data as Report)
    .sort((a: Report, b: Report) => b.meta.date.localeCompare(a.meta.date));
}
