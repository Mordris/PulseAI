import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parse as parseYaml } from "yaml";
import { DEFAULT_SCHEMA_DIR } from "../src/index.ts";

const LABELS_FILE = join(DEFAULT_SCHEMA_DIR, "..", ".github", "labels.yml");

// The labeler action parses labels.yml with a YAML 1.2 library, where an unquoted 5319e7 is a
// number and an unquoted comma ends a value; PyYAML (YAML 1.1) would not notice either.
describe(".github/labels.yml under YAML 1.2", () => {
  const labels: unknown = parseYaml(readFileSync(LABELS_FILE, "utf8"));

  it("is a list of name, color, description string entries", () => {
    expect(Array.isArray(labels)).toBe(true);
    for (const label of labels as Record<string, unknown>[]) {
      expect(Object.keys(label).sort()).toEqual(["color", "description", "name"]);
      expect(typeof label.name).toBe("string");
      expect(typeof label.description).toBe("string");
      expect(typeof label.color).toBe("string");
      expect(label.color).toMatch(/^[0-9a-f]{6}$/);
    }
  });
});
