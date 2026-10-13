import { mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { token } from "@pulseai/tokens";
import { describe, expect, it } from "vitest";
import { parseSiteContext, SiteContextError } from "../src/lib/context.ts";
import { createFormatters } from "../src/lib/format.ts";
import { createTranslator, humanize, interpolate, MissingStringError } from "../src/lib/i18n.ts";
import {
  createReportValidator,
  ReportError,
  readReport,
  reportFiles,
} from "../src/lib/reports-loader.ts";
import { enumAt, rangeAt, requiredAt, SchemaValueError } from "../src/lib/schema-values.ts";
import {
  INSTANCE_ENV,
  requireInstanceDir,
  SiteSetupError,
  siteLocation,
  sitePaths,
} from "../src/lib/setup.ts";
import { jsonForScript } from "../src/lib/theme.ts";
import { categoryColors, mermaidVariables, themeData, vegaConfig } from "../src/lib/theme-data.ts";
import { EXAMPLES, engineContext, engineTokens, REPO, sampleReport } from "./fixtures.ts";

const SITE_SRC = join(REPO, "packages/site/src");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((rel) => rel.endsWith(".astro") || rel.endsWith(".ts") || rel.endsWith(".css"))
    .map((rel) => join(dir, rel));
}

describe("siteLocation", () => {
  it("has no origin and a root base without a site URL", () => {
    expect(siteLocation(null)).toEqual({ base: "/" });
  });

  it("splits a project-site URL into origin and base", () => {
    expect(siteLocation("https://mordris.github.io/PulseAI/")).toEqual({
      site: "https://mordris.github.io",
      base: "/PulseAI/",
    });
  });

  it("adds the trailing slash a base needs", () => {
    expect(siteLocation("https://example.org/reports").base).toBe("/reports/");
    expect(siteLocation("https://example.org").base).toBe("/");
  });
});

describe("site paths", () => {
  it("lays out an instance directory", () => {
    const paths = sitePaths("/srv/instance");
    expect(paths.contextFile).toBe("/srv/instance/.pulse/site-context.json");
    expect(paths.tokensDir).toBe("/srv/instance/.pulse/tokens");
    expect(paths.reportsDir).toBe("/srv/instance/reports");
    expect(paths.outDir).toBe("/srv/instance/dist");
  });

  it("names the wrapper when the instance is not set", () => {
    expect(() => requireInstanceDir({})).toThrow(SiteSetupError);
    expect(() => requireInstanceDir({})).toThrow("scripts/pulse-site.ts build --instance");
    expect(requireInstanceDir({ [INSTANCE_ENV]: "/srv/instance" })).toBe("/srv/instance");
  });
});

describe("translator", () => {
  const t = createTranslator(
    { "ui.hello": "Hello {name}", "ui.count": "{shown} of {total}" },
    "en",
  );

  it("fills placeholders and leaves unknown ones for client code", () => {
    expect(t("ui.hello", { name: "Ada" })).toBe("Hello Ada");
    expect(t("ui.count", { shown: 2 })).toBe("2 of {total}");
    expect(interpolate("{a}{a}", { a: 1 })).toBe("11");
  });

  it("fails on a missing key with the key and language", () => {
    expect(() => t("ui.nope")).toThrow(MissingStringError);
    expect(() => t("ui.nope")).toThrow('missing locale string "ui.nope" for language "en"');
  });

  it("falls back for keys built from data", () => {
    expect(t.or("fields.reading_minutes", humanize("reading_minutes"))).toBe("Reading minutes");
    expect(t.has("ui.hello")).toBe(true);
  });
});

describe("formatters", () => {
  const fmt = createFormatters("en");
  const t = createTranslator(engineContext().strings, "en");

  it("formats calendar dates without shifting the day", () => {
    expect(fmt.date("2026-10-11")).toBe("October 11, 2026");
    expect(fmt.dateShort("2026-10-01")).toBe("Oct 1");
  });

  it("formats timestamps in the report's time zone", () => {
    expect(fmt.dateTime("2026-10-11T14:00:00Z", "Europe/Istanbul")).toBe("Oct 11, 2026, 5:00 PM");
  });

  it("signs changes and formats values of every kind", () => {
    expect(fmt.signed(3)).toBe("+3");
    expect(fmt.signed(-2)).toBe("-2");
    expect(fmt.signed(0)).toBe("0");
    expect(fmt.value(true, t)).toBe("Yes");
    expect(fmt.value(null, t)).toBe("—");
    expect(fmt.value(["a", 1000], t)).toBe("a, 1,000");
  });
});

describe("schema values", () => {
  const schema = {
    properties: { a: { enum: ["x", "y"], required: ["p", "q"], minimum: 1, maximum: 3 } },
  };

  it("reads enums, required lists, and integer ranges", () => {
    expect(enumAt(schema, "properties.a")).toEqual(["x", "y"]);
    expect(requiredAt(schema, "properties.a")).toEqual(["p", "q"]);
    expect(rangeAt(schema, "properties.a")).toEqual([1, 2, 3]);
  });

  it("fails clearly when the schema has no such value", () => {
    expect(() => enumAt(schema, "properties.b")).toThrow(SchemaValueError);
    expect(() => rangeAt(schema, "properties.b")).toThrow("no integer range at properties.b");
  });
});

describe("jsonForScript", () => {
  it("cannot close the script element it lives in", () => {
    const text = jsonForScript({ note: "</script><script>alert(1)</script>" });
    expect(text).not.toContain("</script>");
    expect(JSON.parse(text)).toEqual({ note: "</script><script>alert(1)</script>" });
  });
});

describe("site context", () => {
  it("accepts the context of the engine defaults", () => {
    expect(engineContext().sections.map((section) => section.id)).toEqual([
      "models",
      "tooling",
      "research",
      "oss",
    ]);
  });

  it("names the part of the context that is invalid", () => {
    const context = structuredClone(engineContext()) as unknown as { config: { language: string } };
    context.config.language = "English";
    expect(() => parseSiteContext(context, "ctx.json")).toThrow(SiteContextError);
    expect(() => parseSiteContext(context, "ctx.json")).toThrow("ctx.json: config is invalid");
  });
});

describe("report validation", () => {
  const validate = createReportValidator(engineContext());

  it("accepts every sample edition", () => {
    for (const date of ["2026-10-09", "2026-10-10", "2026-10-11"]) {
      expect(validate(sampleReport(date), date).meta.date).toBe(date);
    }
  });

  it("rejects an unknown section with the file and path", () => {
    const report = sampleReport();
    const first = report.items[0];
    if (first === undefined) throw new Error("fixture changed");
    first.section = "weather";
    expect(() => validate(report, "r.json")).toThrow(ReportError);
    expect(() => validate(report, "r.json")).toThrow(
      'r.json: items/0/section: unknown section "weather"',
    );
  });

  it("rejects notes for an unknown section with the file and path", () => {
    const report = sampleReport();
    report.section_notes = { weather: [{ title: "Lost", text: "No section shows this." }] };
    expect(() => validate(report, "r.json")).toThrow(
      'r.json: section_notes/weather: unknown section "weather"',
    );
  });

  it("rejects a window time zone that is not an IANA name, with the file and path", () => {
    const report = sampleReport();
    report.meta.window.tz = "UTC+3";
    expect(() => validate(report, "r.json")).toThrow(
      'r.json: meta/window/tz: unknown time zone "UTC+3"',
    );
  });

  it("checks each item's detail against its type's schema", () => {
    const report = sampleReport();
    const first = report.items[0];
    if (first === undefined) throw new Error("fixture changed");
    (first.detail as { [key: string]: unknown }).org = 42;
    expect(() => validate(report, "r.json")).toThrow("r.json: items/0/detail/org:");
  });

  it("reports schema problems with their paths", () => {
    const report = sampleReport() as unknown as { headline: unknown };
    report.headline = "";
    expect(() => validate(report, "r.json")).toThrow("r.json: headline:");
  });
});

describe("report files", () => {
  it("finds the sample editions oldest first", () => {
    const files = reportFiles(join(EXAMPLES, "reports"));
    expect(files.map((file) => file.date)).toEqual(["2026-10-09", "2026-10-10", "2026-10-11"]);
  });

  it("rejects a report outside reports/YYYY/MM/DD/", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-reports-"));
    mkdirSync(join(dir, "drafts"));
    writeFileSync(join(dir, "drafts", "report.json"), "{}");
    expect(() => reportFiles(dir)).toThrow("reports live at reports/YYYY/MM/DD/report.json");
  });

  it("rejects a report filed under another date", () => {
    const dir = mkdtempSync(join(tmpdir(), "pulse-reports-"));
    mkdirSync(join(dir, "2026", "10", "12"), { recursive: true });
    const file = join(dir, "2026", "10", "12", "report.json");
    writeFileSync(file, JSON.stringify(sampleReport()));
    const validate = createReportValidator(engineContext());
    expect(() => readReport({ file, date: "2026-10-12" }, validate)).toThrow(
      "meta.date is 2026-10-11, but the file is filed under 2026-10-12",
    );
  });
});

describe("theme data", () => {
  it("themes charts from tokens in both modes", async () => {
    const tokens = await engineTokens();
    const light = vegaConfig(tokens.light);
    expect((light.range as { category: string[] }).category).toEqual(categoryColors(tokens.light));
    expect(categoryColors(tokens.light)).toHaveLength(8);
    expect(categoryColors(tokens.light)[0]).toBe(
      token(tokens.light, "color.chart.category.1").value,
    );
    expect((light.axis as { gridColor: string }).gridColor).toBe(
      token(tokens.light, "color.chart.grid").value,
    );
    const data = themeData(tokens);
    expect(Object.keys(data.vega)).toEqual(["light", "dark"]);
    expect(data.mermaid.dark.primaryTextColor).toBe(token(tokens.dark, "color.text.primary").value);
    expect(mermaidVariables(tokens.light).fontFamily).toContain("Inter Variable");
  });

  it("pads charts by the chart.padding token", async () => {
    const tokens = structuredClone((await engineTokens()).light);
    const padding = tokens.tokens["chart.padding"];
    if (padding === undefined) throw new Error("chart.padding is not a token");
    padding.value = 10;
    expect(vegaConfig(tokens).padding).toBe(10);
  });

  it("orders categorical slots numerically", async () => {
    const tokens = structuredClone((await engineTokens()).light);
    const ten = tokens.tokens["color.chart.category.1"];
    if (ten === undefined) throw new Error("fixture changed");
    tokens.tokens["color.chart.category.10"] = { ...ten, value: "#000000" };
    expect(categoryColors(tokens).at(-1)).toBe("#000000");
  });
});

describe("source rules", () => {
  it("uses only locale strings that exist in every language", () => {
    const keys = new Set<string>();
    for (const file of sourceFiles(SITE_SRC)) {
      for (const match of readFileSync(file, "utf8").matchAll(/\bt\(\s*"([a-z0-9_.-]+)"/g)) {
        if (match[1] !== undefined) keys.add(match[1]);
      }
    }
    expect(keys.size).toBeGreaterThan(0);
    for (const lang of ["en", "tr"]) {
      const strings = JSON.parse(
        readFileSync(join(REPO, "locales", `${lang}.json`), "utf8"),
      ).strings;
      const missing = [...keys].filter((key) => !(key in strings));
      expect(missing, lang).toEqual([]);
    }
  });

  it("has no raw colors outside the token files", () => {
    const raw = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab)\(/i;
    const offenders = sourceFiles(SITE_SRC).flatMap((file) =>
      readFileSync(file, "utf8")
        .split("\n")
        .map((line, index) => ({ line, index }))
        .filter(({ line }) => raw.test(line.replace(/href="#[^"]*"|`#\$\{[^}]*\}`|"#"/g, "")))
        .map(({ index }) => `${relative(SITE_SRC, file)}:${index + 1}`),
    );
    expect(offenders).toEqual([]);
  });
});
