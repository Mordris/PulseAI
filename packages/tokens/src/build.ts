import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { validator } from "@pulseai/contracts";
import { z } from "zod";
import { renderCss, renderCustomMedia } from "./css.ts";
import { ENGINE_TOKENS_DIR, readLayers, TokenError } from "./layers.ts";
import {
  applyOverrides,
  extensionOf,
  findToken,
  leaves,
  missingSectionToken,
  type SectionColor,
  type ThemeOverrides,
} from "./overrides.ts";
import { MODES, type Mode, type ResolvedTokens, resolveMode } from "./resolve.ts";

export interface BuildTokensOptions {
  /** Engine token directory; defaults to the repository's tokens/. */
  engineDir?: string;
  /** Instance directory; its tokens/ folder overrides the engine's, file by file and key by key. */
  instanceDir?: string | undefined;
  preset: string;
  overrides?: ThemeOverrides | undefined;
  sections: readonly SectionColor[];
}

export interface TokenBuild {
  resolved: Record<Mode, ResolvedTokens>;
  css: string;
  /** `@custom-media` rules for the breakpoint tokens. */
  media: string;
  /** Fontsource packages the resolved font families need, sorted. */
  fonts: string[];
}

export const CSS_FILE = "tokens.css";
export const MEDIA_FILE = "media.css";

export function modeFile(mode: Mode): string {
  return `${mode}.json`;
}

export async function buildTokens(options: BuildTokensOptions): Promise<TokenBuild> {
  const engineDir = options.engineDir ?? ENGINE_TOKENS_DIR;
  const resolved: Partial<Record<Mode, ResolvedTokens>> = {};
  const fonts = new Set<string>();
  for (const mode of MODES) {
    const layered = readLayers({
      engineDir,
      instanceDir: options.instanceDir,
      preset: options.preset,
      mode,
      modes: MODES,
    });
    const tree = applyOverrides(layered, options.overrides ?? {}, options.sections);
    for (const section of options.sections) {
      if (findToken(tree, section.color_token) === undefined) {
        throw new TokenError(`${mode}: ${missingSectionToken(section)}`);
      }
    }
    for (const { token } of leaves(tree)) {
      const pkg = extensionOf(token)?.fontsource;
      if (typeof pkg === "string") fonts.add(pkg);
    }
    resolved[mode] = await resolveMode(tree, options.preset, mode);
  }
  const complete = resolved as Record<Mode, ResolvedTokens>;
  return {
    resolved: complete,
    css: renderCss(complete),
    media: renderCustomMedia(complete),
    fonts: [...fonts].sort(),
  };
}

export function writeTokenBuild(build: TokenBuild, outDir: string): void {
  mkdirSync(outDir, { recursive: true });
  writeFileSync(join(outDir, CSS_FILE), build.css);
  writeFileSync(join(outDir, MEDIA_FILE), build.media);
  for (const mode of MODES) {
    writeFileSync(
      join(outDir, modeFile(mode)),
      `${JSON.stringify(build.resolved[mode], null, 2)}\n`,
    );
  }
}

const resolvedValidator = validator("tokens-resolved");

/** Read and validate one mode's resolved tokens from a build directory. */
export function readResolved(dir: string, mode: Mode): ResolvedTokens {
  const path = join(dir, modeFile(mode));
  let data: unknown;
  try {
    data = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new TokenError(`${path}: cannot read resolved tokens (${(error as Error).message})`);
  }
  const result = resolvedValidator.safeParse(data);
  if (!result.success) {
    throw new TokenError(`${path}: invalid resolved tokens\n${z.prettifyError(result.error)}`);
  }
  return data as ResolvedTokens;
}
