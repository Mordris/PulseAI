import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve, sep } from "node:path";
import { z } from "zod";

export type JsonSchema = Parameters<typeof z.fromJSONSchema>[0];

const SUFFIX = ".schema.json";

/**
 * The engine's schema/ directory. It is found through this package's own name, not this file's
 * location, so it stays right when a bundler (the site's server build) moves this module.
 */
export const DEFAULT_SCHEMA_DIR = resolve(
  dirname(createRequire(import.meta.url).resolve("@pulseai/contracts/package.json")),
  "../../schema",
);

/** Every *.schema.json under dir, keyed by relative path without the suffix ("item-types/paper"). */
export function loadSchemas(dir: string = DEFAULT_SCHEMA_DIR): Map<string, JsonSchema> {
  const schemas = new Map<string, JsonSchema>();
  const entries = readdirSync(dir, { recursive: true, encoding: "utf8" });
  for (const entry of entries.sort()) {
    if (!entry.endsWith(SUFFIX) || entry.split(sep).includes("examples")) continue;
    const key = entry.slice(0, -SUFFIX.length).split(sep).join("/");
    schemas.set(key, JSON.parse(readFileSync(join(dir, entry), "utf8")) as JsonSchema);
  }
  return schemas;
}

export function getSchema(name: string, dir: string = DEFAULT_SCHEMA_DIR): JsonSchema {
  const schema = loadSchemas(dir).get(name);
  if (schema === undefined) {
    throw new Error(`unknown schema "${name}" in ${dir}`);
  }
  return schema;
}

export function compile(schema: JsonSchema): z.ZodType {
  return z.fromJSONSchema(schema);
}

export function validator(name: string, dir: string = DEFAULT_SCHEMA_DIR): z.ZodType {
  return compile(getSchema(name, dir));
}

export type * from "./generated/index.ts";
