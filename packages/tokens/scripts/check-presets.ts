/**
 * Build every engine theme preset and run `pulse tokens check` on each: the CI gate for the presets
 * the engine ships. Section colors come from a site context file (`pulse site context`).
 *
 *   node packages/tokens/scripts/check-presets.ts --context <site-context.json> --out <dir>
 */
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { validator } from "@pulseai/contracts";
import {
  buildTokens,
  ENGINE_TOKENS_DIR,
  MODES,
  presetNames,
  type SectionColor,
  writeTokenBuild,
} from "../src/index.ts";

const USAGE = "usage: node packages/tokens/scripts/check-presets.ts --context <file> --out <dir>";

const { values } = parseArgs({ options: { context: { type: "string" }, out: { type: "string" } } });
if (values.context === undefined || values.out === undefined) {
  console.error(USAGE);
  process.exit(2);
}
const context: unknown = JSON.parse(readFileSync(values.context, "utf8"));
if (!validator("site-context").safeParse(context).success) {
  console.error(`${values.context}: not a site context; run "pulse site context" first`);
  process.exit(2);
}
const { sections } = context as { sections: SectionColor[] };

const failed: string[] = [];
for (const preset of presetNames([ENGINE_TOKENS_DIR], MODES)) {
  const dir = resolve(values.out, preset);
  writeTokenBuild(await buildTokens({ preset, sections }), dir);
  console.log(`== ${preset}`);
  const result = spawnSync("uv", ["run", "pulse", "tokens", "check", "--tokens", dir], {
    stdio: "inherit",
  });
  if (result.status !== 0) failed.push(preset);
}
if (failed.length > 0) {
  console.error(`presets failing the token check: ${failed.join(", ")}`);
  process.exitCode = 1;
}
