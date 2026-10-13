import type { RSSFeedItem } from "@astrojs/rss";
import { reportPath } from "./report.ts";
import type { Report } from "./types.ts";

/** Feed items for the newest `limit` editions (reports come newest first), with absolute links. */
export function feedItems(reports: readonly Report[], site: URL, limit: number): RSSFeedItem[] {
  return reports.slice(0, limit).map((report) => ({
    title: report.headline,
    link: new URL(reportPath(report.meta.date), site).href,
    pubDate: new Date(report.meta.window.end),
    description: report.tldr.map((line) => line.text).join(" "),
  }));
}
