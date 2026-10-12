import { existsSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve, sep } from "node:path";

/** A DTCG document or group: nested objects whose leaves carry `$value`. */
export type TokenTree = { [key: string]: unknown };

/** The engine's tokens/ directory, found through the package name (see DEFAULT_SCHEMA_DIR). */
export const ENGINE_TOKENS_DIR = resolve(
  dirname(createRequire(import.meta.url).resolve("@pulseai/tokens/package.json")),
  "../../tokens",
);

const BASE_DIR = "base";
const MODES_DIR = "modes";
const THEMES_DIR = "themes";
const PRESET_BASE = "base.json";

export class TokenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TokenError";
  }
}

function isTree(value: unknown): value is TokenTree {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Deep-merge DTCG trees; later trees win. Arrays and scalars are replaced, objects are merged. */
export function mergeTokens(...trees: TokenTree[]): TokenTree {
  const merged: TokenTree = {};
  for (const tree of trees) {
    for (const [key, value] of Object.entries(tree)) {
      const current = merged[key];
      merged[key] = isTree(current) && isTree(value) ? mergeTokens(current, value) : value;
    }
  }
  return merged;
}

function readTree(path: string): TokenTree {
  let parsed: unknown;
  try {
    parsed = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new TokenError(`${path}: cannot read tokens (${(error as Error).message})`);
  }
  if (!isTree(parsed)) {
    throw new TokenError(`${path}: a token file must be a JSON object`);
  }
  return parsed;
}

/** JSON files directly or deeply under base/, except base/modes/, in a stable order. */
function baseFiles(root: string): string[] {
  const dir = join(root, BASE_DIR);
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((rel) => rel.endsWith(".json") && rel.split(sep)[0] !== MODES_DIR)
    .sort()
    .map((rel) => join(dir, rel));
}

function optional(path: string): string[] {
  return existsSync(path) ? [path] : [];
}

/** Presets that define both modes in any of the roots. */
export function presetNames(roots: string[], modes: readonly string[]): string[] {
  const names = new Set<string>();
  for (const root of roots) {
    const dir = join(root, THEMES_DIR);
    if (!existsSync(dir)) continue;
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory()) names.add(entry.name);
    }
  }
  return [...names]
    .filter((name) =>
      modes.every((mode) =>
        roots.some((root) => existsSync(join(root, THEMES_DIR, name, `${mode}.json`))),
      ),
    )
    .sort();
}

export interface LayerOptions {
  engineDir: string;
  instanceDir?: string | undefined;
  preset: string;
  mode: string;
  modes: readonly string[];
}

/**
 * Token files for one mode, lowest precedence first: for the engine and then the instance,
 * base/**, base/modes/<mode>.json, themes/<preset>/base.json, themes/<preset>/<mode>.json.
 */
export function layerFiles(options: LayerOptions): string[] {
  const roots = [options.engineDir];
  const instanceTokens = options.instanceDir ? join(options.instanceDir, "tokens") : undefined;
  if (instanceTokens && existsSync(instanceTokens)) roots.push(instanceTokens);
  const presets = presetNames(roots, options.modes);
  if (!presets.includes(options.preset)) {
    throw new TokenError(
      `unknown theme preset "${options.preset}"; available: ${presets.join(", ") || "none"}`,
    );
  }
  return roots.flatMap((root) => [
    ...baseFiles(root),
    ...optional(join(root, BASE_DIR, MODES_DIR, `${options.mode}.json`)),
    ...optional(join(root, THEMES_DIR, options.preset, PRESET_BASE)),
    ...optional(join(root, THEMES_DIR, options.preset, `${options.mode}.json`)),
  ]);
}

export function readLayers(options: LayerOptions): TokenTree {
  return mergeTokens(...layerFiles(options).map(readTree));
}
