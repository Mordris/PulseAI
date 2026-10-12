import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import ItemDetail from "../src/components/items/ItemDetail.astro";
import { archiveHeatmap, rankChanges, researchFunnel } from "../src/lib/frame-charts.ts";
import type { RenderContext } from "../src/lib/render.ts";
import type { Item, Report } from "../src/lib/types.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

function item(id: string): Item {
  const found = report.items.find((candidate) => candidate.id === id);
  if (found === undefined) throw new Error(`no item ${id}`);
  return found;
}

async function detail(id: string): Promise<string> {
  const entry = item(id);
  return container.renderToString(ItemDetail, {
    props: { ctx, item: entry, itemType: ctx.itemType(entry.type) },
  });
}

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("type components", () => {
  it("formats a model's key facts with units from the locale", async () => {
    const html = await detail("northwind-atlas-3");
    expect(html).toContain("1,000,000 tokens");
    expect(html).toContain("$2.5 per million tokens");
    expect(html).toContain("Closed");
  });

  it("orders a changelog by the schema's tag order", async () => {
    const html = await detail("relay-cli-3-0");
    const order = ["New", "Fix", "Breaking", "Performance", "Deprecation", "Security"].map((tag) =>
      html.indexOf(`>${tag}</span>`),
    );
    expect(order.every((index) => index >= 0)).toBe(true);
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("lists a paper's artifacts and marks the missing ones", async () => {
    const html = await detail("verify-then-expand");
    expect(html).toContain("https://example.org/papers/verify-then-expand/code");
    expect(html).toContain("Not released");
    expect(html).toContain("Intermediate");
  });

  it("draws an advisory's CVSS on the schema's scale", async () => {
    const html = await detail("pyfetchkit-path-traversal");
    expect(html).toMatch(/<meter[^>]*max="10"[^>]*value="9.1"/);
    expect(html).toContain("--pulse-color-severity-critical");
  });

  it("draws rank changes as a chart", async () => {
    const html = await detail("open-agents-leaderboard");
    expect(html).toContain('id="visual-open-agents-leaderboard-ranks"');
  });
});

describe("frame charts", () => {
  it("sizes archive cells from a token and labels from locales", () => {
    const visual = archiveHeatmap([{ date: "2026-10-11", score: 45 }], ctx);
    const spec = visual.spec as { width: { step: number }; encoding: { color: { title: string } } };
    expect(spec.width.step).toBe(ctx.tokenNumber("chart.heatmap_cell"));
    expect(spec.encoding.color.title).toBe("Pulse score");
  });

  it("lists funnel stages in the schema's order", () => {
    const visual = researchFunnel(report.meta.stats, ctx);
    const values = (visual.spec as { data: { values: { stage: string; count: number }[] } }).data
      .values;
    expect(values.map((value) => value.stage)).toEqual([
      "Scanned",
      "Triaged",
      "Verified",
      "Published",
    ]);
    expect(visual.alt).toContain("412 scanned");
  });

  it("plots a new entry at its rank after the change only", () => {
    const visual = rankChanges(
      "board",
      "Board",
      [
        { name: "New", after: 1 },
        { name: "Old", before: 1, after: 2 },
      ],
      ctx,
    );
    const values = (visual.spec as { data: { values: { name: string }[] } }).data.values;
    expect(values.filter((value) => value.name === "New")).toHaveLength(1);
    expect(values.filter((value) => value.name === "Old")).toHaveLength(2);
  });
});
