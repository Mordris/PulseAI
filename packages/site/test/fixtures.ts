import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { DEFAULT_SCHEMA_DIR } from "@pulseai/contracts";
import { buildTokens, type Mode, type ResolvedTokens } from "@pulseai/tokens";
import { parse } from "yaml";
import { parseSiteContext, type SiteContext } from "../src/lib/context.ts";
import { createRenderContext, type RenderContext } from "../src/lib/render.ts";
import type { Report } from "../src/lib/types.ts";

export const REPO = resolve(DEFAULT_SCHEMA_DIR, "..");
export const EXAMPLES = join(REPO, "examples");

function read<T>(relative: string): T {
  const text = readFileSync(join(REPO, relative), "utf8");
  return (relative.endsWith(".json") ? JSON.parse(text) : parse(text)) as T;
}

/**
 * The context `pulse site context` writes for the engine defaults (no instance), assembled from
 * the registry files so the site's tests run without Python. Validated like a real context.
 */
export function engineContext(): SiteContext {
  const itemTypes = read<{ item_types: SiteContext["item_types"] }>(
    "taxonomy/item-types.yaml",
  ).item_types;
  const schemas: SiteContext["schemas"] = {
    "report.schema.json": read("schema/report.schema.json"),
  };
  for (const file of readdirSync(join(REPO, "schema/item-types")).sort()) {
    schemas[`item-types/${file}`] = read(`schema/item-types/${file}`);
  }
  const sections = read<{ sections: SiteContext["sections"] }>("taxonomy/sections.yaml").sections;
  const context = {
    schema_version: 1,
    engine_version: "0.0.0-test",
    config: read("defaults/pulse.config.yaml"),
    sections: [...sections].sort((a, b) => a.order - b.order || a.id.localeCompare(b.id)),
    item_types: itemTypes,
    strings: read<{ strings: SiteContext["strings"] }>("locales/en.json").strings,
    schemas,
  };
  return parseSiteContext(context, "engine defaults");
}

let tokens: Promise<Record<Mode, ResolvedTokens>> | undefined;

export function engineTokens(): Promise<Record<Mode, ResolvedTokens>> {
  tokens ??= buildTokens({ preset: "pulse", sections: engineContext().sections }).then(
    (build) => build.resolved,
  );
  return tokens;
}

export async function testContext(base = "/"): Promise<RenderContext> {
  return createRenderContext(engineContext(), await engineTokens(), base);
}

/** A sample edition from examples/ (the showcase is 2026-10-11). */
export function sampleReport(date = "2026-10-11"): Report {
  return JSON.parse(
    readFileSync(join(EXAMPLES, "reports", ...date.split("-"), "report.json"), "utf8"),
  ) as Report;
}
