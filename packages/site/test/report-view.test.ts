import { experimental_AstroContainer as AstroContainer } from "astro/container";
import { beforeAll, describe, expect, it } from "vitest";
import Corrections from "../src/components/frame/Corrections.astro";
import ReportView from "../src/components/frame/ReportView.astro";
import Signals from "../src/components/frame/Signals.astro";
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

describe("report view", () => {
  it("renders nothing for empty signals and corrections", async () => {
    expect((await container.renderToString(Signals, { props: { ctx, signals: [] } })).trim()).toBe(
      "",
    );
    expect(
      (await container.renderToString(Corrections, { props: { ctx, corrections: [] } })).trim(),
    ).toBe("");
  });

  it("renders sections in registry order with the research groups", async () => {
    const html = await container.renderToString(ReportView, { props: { ctx, report } });
    const sections = ctx.sections.map((section) => html.indexOf(`id="section-${section.id}"`));
    expect(sections.every((index) => index >= 0)).toBe(true);
    expect(sections).toEqual([...sections].sort((a, b) => a - b));
    for (const group of ["Paper of the day", "Top papers", "Also notable", "Long reads"]) {
      expect(html).toContain(group);
    }
    expect(html).toContain("data-pagefind-body");
  });

  it("keeps the front page out of the search index", async () => {
    const html = await container.renderToString(ReportView, {
      props: { ctx, report, searchable: false },
    });
    expect(html).not.toContain("data-pagefind-body");
  });
});
