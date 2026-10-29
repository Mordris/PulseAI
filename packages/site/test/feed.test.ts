import { describe, expect, it } from "vitest";
import { feedItems } from "../src/lib/feed.ts";
import { sampleReport } from "./fixtures.ts";

describe("feed", () => {
  const reports = ["2026-10-11", "2026-10-10", "2026-10-09"].map((date) => sampleReport(date));
  const site = new URL("https://example.org/PulseAI/");

  it("lists the newest editions, up to the limit, with absolute links", () => {
    const items = feedItems(reports, site, 2);
    expect(items.map((item) => item.link)).toEqual([
      "https://example.org/PulseAI/2026/10/11/",
      "https://example.org/PulseAI/2026/10/10/",
    ]);
    expect(items[0]).toMatchObject({ title: reports[0]?.headline });
  });

  it("lists every edition when there are fewer than the limit", () => {
    expect(feedItems(reports, site, 30)).toHaveLength(3);
  });
});
