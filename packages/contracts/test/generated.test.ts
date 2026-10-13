import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, expectTypeOf, it } from "vitest";
import { generateTypes, OUT_DIR } from "../scripts/generate-types.ts";
import { DEFAULT_SCHEMA_DIR, type ReportSchema, type SectionsSchema } from "../src/index.ts";

function readTree(dir: string): Map<string, string> {
  const files = new Map<string, string>();
  for (const rel of readdirSync(dir, { recursive: true, encoding: "utf8" })) {
    if (rel.endsWith(".ts")) {
      files.set(rel.split("\\").join("/"), readFileSync(join(dir, rel), "utf8"));
    }
  }
  return files;
}

describe("generated types", () => {
  it("are current (run: pnpm --filter @pulseai/contracts generate)", async () => {
    const expected = await generateTypes();
    const actual = readTree(OUT_DIR);
    expect([...actual.keys()].sort()).toEqual([...expected.keys()].sort());
    for (const [file, text] of expected) {
      expect(actual.get(file), file).toBe(text);
    }
  });

  it("names types after schema titles", () => {
    expectTypeOf<ReportSchema.Report["schema_version"]>().toEqualTypeOf<1>();
    expectTypeOf<ReportSchema.Item["confidence"]>().toEqualTypeOf<
      "confirmed" | "reported" | "rumor"
    >();
    expectTypeOf<ReportSchema.DashboardVisual["kind"]>().toEqualTypeOf<"dashboard">();
    expectTypeOf<SectionsSchema.Section["order"]>().toEqualTypeOf<number>();
  });
});

describe("schema directory", () => {
  it("is found through the package name, so bundling this module keeps it right", () => {
    expect(DEFAULT_SCHEMA_DIR).toBe(
      resolve(fileURLToPath(new URL("../../../schema", import.meta.url))),
    );
  });
});
