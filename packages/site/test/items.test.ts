import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import Block from "../src/components/blocks/Block.astro";
import ItemDetail from "../src/components/items/ItemDetail.astro";
import ItemShell from "../src/components/items/ItemShell.astro";
import type { RenderContext } from "../src/lib/render.ts";
import {
  blockVisuals,
  groupItems,
  itemDepth,
  leafVisuals,
  looseVisuals,
  matchesGroup,
  reportPath,
} from "../src/lib/report.ts";
import type { Item, Report } from "../src/lib/types.ts";
import { engineContext, sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

function item(id: string): Item {
  const found = report.items.find((candidate) => candidate.id === id);
  if (found === undefined) throw new Error(`no item ${id}`);
  return found;
}

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("report helpers", () => {
  const report = sampleReport();
  const research = engineContext().sections.find((section) => section.id === "research");
  if (research === undefined) throw new Error("no research section");
  const items = report.items.filter((item) => item.section === "research");

  it("splits items into deep dives and briefs at deep_dive.min_impact", () => {
    const [deep, brief] = [items.find((i) => i.impact >= 3), items.find((i) => i.impact < 3)];
    expect(deep && itemDepth(deep, 3)).toBe("deep");
    expect(brief && itemDepth(brief, 3)).toBe("brief");
  });

  it("puts each item in the first group it matches, in registry order", () => {
    const groups = groupItems(research, items, report.featured, 3);
    expect(groups.map((g) => [g.group?.id, g.items.map((i) => i.id)])).toEqual([
      ["paper_of_the_day", ["verify-then-expand"]],
      ["top_papers", ["sparse-memory-routing"]],
      ["also_notable", ["tool-use-eval-survey"]],
      ["long_reads", ["agents-in-production-year-one"]],
    ]);
  });

  it("requires every condition of a match", () => {
    const paper = items.find((item) => item.id === "verify-then-expand");
    const group = research.groups.find((g) => g.id === "paper_of_the_day");
    if (paper === undefined || group === undefined) throw new Error("fixture changed");
    expect(matchesGroup(paper, group, report.featured, 3)).toBe(true);
    expect(matchesGroup(paper, group, {}, 3)).toBe(false);
  });

  it("keeps unmatched items after the groups and drops empty groups", () => {
    const article = items.filter((item) => item.type === "article");
    const other = { ...research, groups: research.groups.filter((g) => g.id !== "long_reads") };
    const groups = groupItems(other, article, report.featured, 3);
    expect(groups).toEqual([{ group: undefined, items: article }]);
  });

  it("separates visuals placed in blocks from loose ones", () => {
    const atlas = report.items.find((item) => item.id === "northwind-atlas-3");
    if (atlas === undefined) throw new Error("fixture changed");
    expect(blockVisuals(atlas, "benchmarks").map((v) => v.id)).toEqual(["atlas-3-benchmarks"]);
    expect(looseVisuals(atlas, ["key_facts"]).map((v) => v.id)).toEqual([
      "atlas-3-benchmarks",
      "atlas-price-comparison",
    ]);
  });

  it("maps a date to its route and a dashboard to its leaf visuals", () => {
    expect(reportPath("2026-10-11")).toBe("2026/10/11/");
    const [dashboard] = report.front_page;
    if (dashboard === undefined) throw new Error("fixture changed");
    expect(leafVisuals(dashboard).map((v) => v.kind)).toEqual(["vega-lite", "table"]);
  });
});

describe("item shell", () => {
  it("renders every showcase item with its type's blocks", async () => {
    for (const entry of report.items) {
      const html = await container.renderToString(ItemShell, { props: { ctx, item: entry } });
      expect(html).toContain(`id="${entry.id}"`);
      expect(html).toContain(`data-depth="${entry.impact >= ctx.minImpact ? "deep" : "brief"}"`);
      for (const visual of entry.visuals) {
        if (visual.block !== undefined)
          expect(html, `${entry.id} ${visual.id}`).toContain(`data-block="${visual.block}"`);
      }
    }
  });

  it("shows brief fields instead of blocks below the deep-dive threshold", async () => {
    const html = await container.renderToString(ItemShell, {
      props: { ctx, item: item("quillmark-1-8-4") },
    });
    expect(html).toContain("Quillmark");
    expect(html).not.toContain("data-block=");
  });

  it("shows a brief item's visuals, whether or not they name a block", async () => {
    const [placed, loose] = item("northwind-atlas-3").visuals;
    if (placed === undefined || loose === undefined) throw new Error("fixture changed");
    const { block: _block, ...unplaced } = loose;
    const brief = {
      ...item("quillmark-1-8-4"),
      visuals: [{ ...placed, block: "benchmarks" }, unplaced],
    };
    const html = await container.renderToString(ItemShell, { props: { ctx, item: brief } });
    expect(html).toContain(`id="visual-${placed.id}"`);
    expect(html).toContain(`id="visual-${loose.id}"`);
    expect(html).not.toContain("data-block=");
  });

  it("links an update to the item it follows up on", async () => {
    const html = await container.renderToString(ItemShell, {
      props: { ctx, item: item("relay-cli-3-0") },
    });
    expect(html).toContain('href="/PulseAI/2026/10/10/#relay-cli-3-rc"');
  });

  it("badges a confidence other than the default", async () => {
    const [signal] = report.signals;
    if (signal === undefined) throw new Error("fixture changed");
    const html = await container.renderToString(ItemShell, { props: { ctx, item: signal } });
    expect(html).toContain("Reported");
    expect(html).toContain("--pulse-color-confidence-reported");
  });
});

describe("item detail", () => {
  it("falls back to GenericDetail for a component that does not exist", async () => {
    const atlas = item("northwind-atlas-3");
    const itemType = { ...ctx.itemType(atlas.type), component: "Missing" } as NonNullable<
      ReturnType<RenderContext["itemType"]>
    >;
    const html = await container.renderToString(ItemDetail, {
      props: { ctx, item: atlas, itemType },
    });
    expect(html).toContain("Northwind Labs");
    expect(html).toContain('data-block="benchmarks"');
  });

  it("renders assigned visuals for a block the component does not know", async () => {
    const atlas = item("northwind-atlas-3");
    const placed = {
      ...atlas,
      visuals: atlas.visuals.map((visual) => ({ ...visual, block: "archive_history" })),
    };
    const html = await container.renderToString(ItemDetail, {
      props: { ctx, item: placed, itemType: ctx.itemType(atlas.type) },
    });
    expect(html).toContain('data-block="archive_history"');
  });

  it("renders nothing for a block with no content and no visuals", async () => {
    const html = await container.renderToString(Block, {
      props: { ctx, item: item("rillet-5-0"), id: "cadence" },
    });
    expect(html.trim()).toBe("");
  });
});
