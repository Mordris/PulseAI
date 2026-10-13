/**
 * Generate TypeScript types from schema/*.schema.json, the single source of truth.
 *
 *   node scripts/generate-types.ts          # rewrite src/generated/
 *   node scripts/generate-types.ts --check  # exit 1 when src/generated/ is stale
 */
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";
import { loadSchemas } from "../src/index.ts";

export const OUT_DIR = fileURLToPath(new URL("../src/generated/", import.meta.url));

const HEADER =
  "/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */\n\n";

type CompileInput = Parameters<typeof compile>[0];

/** "item-types/paper" -> "ItemTypesPaperSchema". */
export function namespaceName(key: string): string {
  const words = key.split(/[/_-]/).filter((word) => word.length > 0);
  return `${words.map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join("")}Schema`;
}

/** Generated file contents keyed by path relative to OUT_DIR ("report.ts", "item-types/paper.ts"). */
export async function generateTypes(): Promise<Map<string, string>> {
  const files = new Map<string, string>();
  const barrel: string[] = [];
  for (const [key, schema] of loadSchemas()) {
    const types = await compile(schema as CompileInput, key, {
      bannerComment: "",
      additionalProperties: false,
      strictIndexSignatures: true,
      unreachableDefinitions: false,
      style: { printWidth: 100 },
    });
    files.set(`${key}.ts`, HEADER + types);
    barrel.push(`export type * as ${namespaceName(key)} from "./${key}.ts";`);
  }
  files.set("index.ts", `${HEADER + barrel.join("\n")}\n`);
  return files;
}

function readTree(dir: string): Map<string, string> {
  const files = new Map<string, string>();
  let entries: string[];
  try {
    entries = readdirSync(dir, { recursive: true, encoding: "utf8" });
  } catch {
    return files;
  }
  for (const rel of entries) {
    if (rel.endsWith(".ts")) {
      files.set(rel.split("\\").join("/"), readFileSync(join(dir, rel), "utf8"));
    }
  }
  return files;
}

async function main(argv: string[]): Promise<number> {
  const files = await generateTypes();
  if (argv.includes("--check")) {
    const current = readTree(OUT_DIR);
    const names = new Set([...files.keys(), ...current.keys()]);
    const stale = [...names].filter((name) => files.get(name) !== current.get(name)).sort();
    if (stale.length > 0) {
      console.error(`stale generated types: ${stale.join(", ")}`);
      console.error("run: pnpm --filter @pulseai/contracts generate");
      return 1;
    }
    return 0;
  }
  rmSync(OUT_DIR, { recursive: true, force: true });
  for (const [rel, text] of files) {
    const target = join(OUT_DIR, rel);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, text);
  }
  return 0;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}
