import { parse, View } from "vega";
import { compile, type TopLevelSpec } from "vega-lite";
import { afterEach, describe, expect, it, vi } from "vitest";
import { chartSpec, embedOptions } from "../src/lib/chart-embed.ts";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("chart embedding", () => {
  it("drops embed options a spec carries in usermeta", () => {
    const spec = chartSpec({
      mark: "bar",
      data: { values: [{ a: 1 }] },
      usermeta: { embedOptions: { patch: "https://patch.example.invalid/patch.json" } },
    });
    expect(spec).not.toHaveProperty("usermeta");
    expect(spec).toMatchObject({ width: "container", mark: "bar" });
  });

  it("keeps a width the spec sets", () => {
    expect(chartSpec({ mark: "bar", width: 120 })).toMatchObject({ width: 120 });
  });

  it("reads every spec as Vega-Lite, whatever its $schema says", () => {
    expect(embedOptions({}).mode).toBe("vega-lite");
  });

  it("refuses every load, so a spec cannot reach the network", async () => {
    const { loader } = embedOptions({});
    await expect(loader.load("https://beacon.example.invalid/data.json")).rejects.toThrow(
      "inline data only",
    );
    await expect(
      loader.sanitize("https://beacon.example.invalid/image.png", { context: "image" }),
    ).rejects.toThrow("inline data only");
  });

  it("runs a chart with remote data without fetching it", async () => {
    const fetch = vi.spyOn(globalThis, "fetch");
    const spec: TopLevelSpec = {
      data: { url: "https://beacon.example.invalid/data.json" },
      mark: "bar",
      encoding: { x: { field: "a", type: "nominal" } },
    };
    const view = new View(parse(compile(spec).spec), {
      loader: embedOptions({}).loader,
      renderer: "none",
      logLevel: 0,
    });
    await view.runAsync().catch(() => undefined);
    view.finalize();
    expect(fetch).not.toHaveBeenCalled();
  });
});
