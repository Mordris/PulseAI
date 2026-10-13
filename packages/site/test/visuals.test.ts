import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import Dashboard from "../src/components/visuals/Dashboard.astro";
import Mermaid from "../src/components/visuals/Mermaid.astro";
import VegaLite from "../src/components/visuals/VegaLite.astro";
import type { RenderContext } from "../src/lib/render.ts";
import { sparkline } from "../src/lib/sparkline.ts";
import type { Report } from "../src/lib/types.ts";
import { inlineTable } from "../src/lib/visual-data.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("inline chart data", () => {
  it("reads top-level values, layers, and named datasets", () => {
    expect(
      inlineTable({
        data: {
          values: [
            { a: 1, b: 2 },
            { a: 3, c: 4 },
          ],
        },
      }),
    ).toEqual({
      columns: ["a", "b", "c"],
      rows: [
        [1, 2, null],
        [3, null, 4],
      ],
    });
    expect(
      inlineTable({ layer: [{ mark: "rule" }, { data: { values: [{ x: 1 }] } }] })?.rows,
    ).toEqual([[1]]);
    expect(inlineTable({ datasets: { d: [{ y: 2 }] } })?.columns).toEqual(["y"]);
  });

  it("has nothing to show for a spec without inline rows", () => {
    expect(inlineTable({ mark: "bar" })).toBeUndefined();
    expect(inlineTable({ data: { values: [] } })).toBeUndefined();
    expect(inlineTable("not a spec")).toBeUndefined();
  });
});

describe("sparkline", () => {
  it("needs two values and centres a flat series", () => {
    expect(sparkline([4], 100, 20, 2)).toBeUndefined();
    expect(sparkline([4, 4], 100, 20, 2)?.points).toBe("2,10 98,10");
  });

  it("spans the box and ends at the last value", () => {
    const line = sparkline([0, 10, 5], 100, 20, 0);
    expect(line?.points).toBe("0,20 50,0 100,10");
    expect(line?.last).toEqual({ x: 100, y: 10 });
  });
});

describe("visuals", () => {
  it("renders a chart over an open data table, with its spec escaped", async () => {
    const visual = {
      kind: "vega-lite" as const,
      id: "escape",
      title: "Escape",
      alt: "A chart",
      source_note: "Test",
      spec: { data: { values: [{ label: "</script>", value: 1 }] }, mark: "bar" },
    };
    const html = await container.renderToString(VegaLite, { props: { ctx, visual } });
    expect(html).toContain('<details class="visual__data" data-chart-table open');
    expect(html).toContain("\\u003c/script>");
    expect(html).toContain('role="img" aria-label="A chart"');
  });

  it("renders a diagram as alt text and source until it is drawn", async () => {
    const paper = report.items.find((candidate) => candidate.id === "verify-then-expand");
    const visual = paper?.visuals.find((candidate) => candidate.kind === "mermaid");
    const html = await container.renderToString(Mermaid, { props: { ctx, visual } });
    expect(html).toContain("data-diagram-fallback");
    expect(html).toContain("flowchart LR");
  });

  it("lays dashboard tiles on its columns", async () => {
    const [dashboard] = report.front_page;
    const html = await container.renderToString(Dashboard, { props: { ctx, visual: dashboard } });
    expect(html).toContain("--columns: 3");
    expect(html).toContain("--span: 2");
    expect(html).toContain('data-visual="table"');
  });
});
