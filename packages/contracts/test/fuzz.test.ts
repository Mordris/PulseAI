import { readFileSync } from "node:fs";
import { join } from "node:path";
import fc from "fast-check";
import { describe, expect, it } from "vitest";
import {
  compile,
  DEFAULT_SCHEMA_DIR,
  loadSchemas,
  type ReportSchema,
  validator,
} from "../src/index.ts";

type Report = ReportSchema.Report;

function firstSource(doc: Report): ReportSchema.ItemSource {
  const source = doc.items[0]?.sources[0];
  if (!source) throw new Error("the fixture must contain a source");
  return source;
}

const sample: Report = JSON.parse(
  readFileSync(join(DEFAULT_SCHEMA_DIR, "examples/report/valid/minimal.json"), "utf8"),
);
const report = validator("report");
const json = fc.jsonValue({ maxDepth: 4 });

describe("untrusted JSON fuzzing", () => {
  const validators = [...loadSchemas()].map(([name, schema]) => [name, compile(schema)] as const);

  it("every schema handles arbitrary JSON without throwing or mutating it", () => {
    fc.assert(
      fc.property(json, (value) => {
        const before = structuredClone(value);
        for (const [name, check] of validators) {
          expect(typeof check.safeParse(value).success, name).toBe("boolean");
          expect(value, name).toEqual(before);
        }
      }),
    );
  });

  const targets = {
    report: (doc: Report) => doc,
    metadata: (doc: Report) => doc.meta,
    window: (doc: Report) => doc.meta.window,
    item: (doc: Report) => doc.items[0],
    source: (doc: Report) => doc.items[0]?.sources[0],
    visual: (doc: Report) => doc.items[0]?.visuals[0],
  };

  for (const [name, target] of Object.entries(targets)) {
    it(`rejects arbitrary extra fields in ${name} without silently stripping them`, () => {
      expect(report.safeParse(sample).success).toBe(true);
      fc.assert(
        fc.property(fc.string(), json, (key, value) => {
          const doc = structuredClone(sample);
          const object = target(doc);
          if (!object) throw new Error(`the fixture must contain ${name}`);
          Object.assign(object, { [`unregistered_${key}`]: value });
          const before = structuredClone(doc);
          expect(report.safeParse(doc).success).toBe(false);
          expect(doc).toEqual(before);
        }),
      );
    });
  }

  it("accepts generated web source URLs", () => {
    fc.assert(
      fc.property(fc.webUrl(), (url) => {
        const doc = structuredClone(sample);
        firstSource(doc).url = url;
        expect(report.safeParse(doc).success).toBe(true);
      }),
    );
  });

  it("rejects generated non-web source URLs", () => {
    fc.assert(
      fc.property(
        fc.constantFrom("javascript:", "data:", "file:", "ftp:", "//"),
        fc.string(),
        (scheme, payload) => {
          const doc = structuredClone(sample);
          firstSource(doc).url = `${scheme}${payload}`;
          expect(report.safeParse(doc).success).toBe(false);
        },
      ),
    );
  });
});
