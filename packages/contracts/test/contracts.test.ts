import { globSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { applyPatch, type Operation } from "rfc6902";
import { describe, expect, it } from "vitest";
import { parse as parseYaml } from "yaml";
import { compile, DEFAULT_SCHEMA_DIR, getSchema, loadSchemas, validator } from "../src/index.ts";

const ROOT = join(DEFAULT_SCHEMA_DIR, "..");

function readData(relative: string): unknown {
  const text = readFileSync(join(ROOT, relative), "utf8");
  return relative.endsWith(".json") ? JSON.parse(text) : parseYaml(text);
}

interface CatalogEntry {
  id: string;
  schema: string;
  paths: string[];
}

interface PatchCase {
  name: string;
  patch: Operation[];
}

describe("schemas", () => {
  const schemas = loadSchemas();

  it("loads top-level and item-type schemas", () => {
    expect(schemas.has("config")).toBe(true);
    expect(schemas.has("report")).toBe(true);
    expect([...schemas.keys()].some((k) => k.startsWith("item-types/"))).toBe(true);
  });

  for (const [name, schema] of schemas) {
    it(`compiles ${name}`, () => {
      expect(() => compile(schema)).not.toThrow();
    });
  }
});

describe("engine data validates in TypeScript", () => {
  const catalog = readData("defaults/registries.yaml") as { registries: CatalogEntry[] };
  for (const entry of catalog.registries) {
    const check = validator(entry.schema.replace(/\.schema\.json$/, ""));
    for (const pattern of entry.paths) {
      for (const file of globSync(pattern.replace("{language}", "*"), { cwd: ROOT })) {
        it(`${entry.id}: ${file}`, () => {
          const result = check.safeParse(readData(file));
          expect(result.success, JSON.stringify(result.error?.issues)).toBe(true);
        });
      }
    }
  }
});

describe("report examples", () => {
  const report = validator("report");
  const minimal = readData("schema/examples/report/valid/minimal.json");

  it("accepts the minimal example", () => {
    expect(report.safeParse(minimal).success).toBe(true);
  });

  const cases = readData("schema/examples/report/invalid-schema.json") as PatchCase[];
  for (const testCase of cases) {
    it(`rejects: ${testCase.name}`, () => {
      const doc = structuredClone(minimal);
      const errors = applyPatch(doc, testCase.patch).filter((e) => e !== null);
      expect(errors).toEqual([]);
      expect(report.safeParse(doc).success).toBe(false);
    });
  }

  it("validates item details with the item-type schema", () => {
    const paper = validator("item-types/paper");
    const doc = minimal as { items: { detail: unknown }[] };
    expect(paper.safeParse(doc.items[1]?.detail).success).toBe(true);
    expect(getSchema("item-types/paper")).toHaveProperty("title", "PaperDetail");
  });
});

// The collect output schemas lean on oneOf, which Zod reads differently from JSON Schema
// validators, so the same examples and patch cases that Python checks run here too.
describe.each(["collected", "collect-run"])("%s examples", (name) => {
  const check = validator(name);
  const minimal = readData(`schema/examples/${name}/valid/minimal.json`);

  it("accepts the minimal example", () => {
    const result = check.safeParse(minimal);
    expect(result.success, JSON.stringify(result.error?.issues)).toBe(true);
  });

  const cases = readData(`schema/examples/${name}/invalid-schema.json`) as PatchCase[];
  for (const testCase of cases) {
    it(`rejects: ${testCase.name}`, () => {
      const doc = structuredClone(minimal);
      const errors = applyPatch(doc, testCase.patch).filter((e) => e !== null);
      expect(errors).toEqual([]);
      expect(check.safeParse(doc).success).toBe(false);
    });
  }
});
