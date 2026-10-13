import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import ActionList from "../src/components/frame/ActionList.astro";
import AdoptionRadar from "../src/components/frame/AdoptionRadar.astro";
import FrontPage from "../src/components/frame/FrontPage.astro";
import KpiTiles from "../src/components/frame/KpiTiles.astro";
import Masthead from "../src/components/frame/Masthead.astro";
import Tldr from "../src/components/frame/Tldr.astro";
import type { RenderContext } from "../src/lib/render.ts";
import type { Report } from "../src/lib/types.ts";
import { sampleReport, testContext } from "./fixtures.ts";

let container: AstroContainer;
let ctx: RenderContext;
let report: Report;

beforeAll(async () => {
  container = await AstroContainer.create();
  ctx = await testContext("/PulseAI/");
  report = sampleReport();
});

describe("report top", () => {
  it("renders nothing for empty regions", async () => {
    const empty = [
      [KpiTiles, { ctx, kpis: [] }],
      [Tldr, { ctx, lines: [] }],
      [AdoptionRadar, { ctx, entries: [], items: [] }],
      [FrontPage, { ctx, visuals: [] }],
      [ActionList, { ctx, actions: [] }],
    ] as const;
    for (const [component, props] of empty) {
      expect((await container.renderToString(component, { props })).trim()).toBe("");
    }
  });

  it("orders radar rings as the schema does", async () => {
    const html = await container.renderToString(AdoptionRadar, {
      props: { ctx, entries: report.adoption_radar, items: report.items },
    });
    const order = ["Adopt", "Trial", "Assess", "Hold"].map((label) => html.indexOf(label));
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("marks a sample edition and compares the score with the 7-day average", async () => {
    const html = await container.renderToString(Masthead, { props: { ctx, report } });
    expect(html).toContain("Sample edition");
    expect(html).toContain("+33.5 against the 7-day average of 11.5");
    const first = sampleReport("2026-10-09");
    expect(await container.renderToString(Masthead, { props: { ctx, report: first } })).toContain(
      "No 7-day average yet",
    );
  });
});
