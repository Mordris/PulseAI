import { compile, getSchema, type JsonSchema, type TokensResolvedSchema } from "@pulseai/contracts";
import StyleDictionary from "style-dictionary";
import type { DesignTokens } from "style-dictionary/types";
import { z } from "zod";
import { TokenError, type TokenTree } from "./layers.ts";
import { EXTENSION, extensionOf, leaves } from "./overrides.ts";

export type ResolvedTokens = TokensResolvedSchema.ResolvedTokens;
export type ResolvedToken = TokensResolvedSchema.ResolvedToken;
export type Mode = ResolvedTokens["mode"];

/** CSS custom properties are named --<prefix>-<token path in kebab case>. */
export const CSS_PREFIX = "pulse";

interface ResolvedSchemaShape {
  properties: { mode: { enum: Mode[] } };
  $defs: { [name: string]: unknown };
}

const resolvedSchema = getSchema("tokens-resolved");
const shape = resolvedSchema as unknown as ResolvedSchemaShape;

/** Theme modes, in the order the schema lists them; the first is the default. */
export const MODES: readonly Mode[] = shape.properties.mode.enum;

/** The mode the OS dark setting selects: the one named after the CSS `prefers-color-scheme` keyword. */
export const OS_DARK = "dark" satisfies Mode;

const resolvedValidator = compile(resolvedSchema);
const extensionValidator = compile({
  ...(shape.$defs.extensions as object),
  $defs: shape.$defs,
} as JsonSchema);

function checkExtensions(tree: TokenTree): void {
  for (const { path, token } of leaves(tree)) {
    const extension = extensionOf(token);
    if (extension === undefined) continue;
    const result = extensionValidator.safeParse(extension);
    if (!result.success) {
      throw new TokenError(
        `${path.join(".")}: invalid $extensions["${EXTENSION}"]\n${z.prettifyError(result.error)}`,
      );
    }
  }
}

/** Resolve aliases and CSS values for one mode with Style Dictionary. */
export async function resolveMode(
  tree: TokenTree,
  preset: string,
  mode: Mode,
): Promise<ResolvedTokens> {
  checkExtensions(tree);
  const dictionary = new StyleDictionary({
    tokens: tree as DesignTokens,
    usesDtcg: true,
    log: { verbosity: "silent", warnings: "error", errors: { brokenReferences: "throw" } },
    platforms: { css: { transformGroup: "css", prefix: CSS_PREFIX } },
  });
  let all: Awaited<ReturnType<typeof dictionary.getPlatformTokens>>["allTokens"];
  try {
    all = (await dictionary.getPlatformTokens("css")).allTokens;
  } catch (error) {
    throw new TokenError(`${preset} ${mode}: ${(error as Error).message.trim()}`);
  }
  const tokens: { [path: string]: ResolvedToken } = {};
  for (const token of all) {
    const path = token.path.join(".");
    const value: unknown = token.$value;
    if (typeof value !== "string" && typeof value !== "number") {
      throw new TokenError(`${path}: $type "${String(token.$type)}" has no CSS value`);
    }
    const extension = token.$extensions?.[EXTENSION] as ResolvedToken["extensions"] | undefined;
    tokens[path] = {
      value,
      type: String(token.$type),
      name: `--${token.name}`,
      ...(extension === undefined ? {} : { extensions: extension }),
    };
  }
  const resolved: ResolvedTokens = { schema_version: 1, preset, mode, tokens };
  const result = resolvedValidator.safeParse(resolved);
  if (!result.success) {
    throw new TokenError(
      `${preset} ${mode}: resolved tokens are invalid\n${z.prettifyError(result.error)}`,
    );
  }
  return resolved;
}

/** One resolved token; fails with the theme and path when it is missing. */
export function token(resolved: ResolvedTokens, path: string): ResolvedToken {
  const found = resolved.tokens[path];
  if (found === undefined) {
    throw new TokenError(
      `token "${path}" is not defined in the ${resolved.preset} ${resolved.mode} theme`,
    );
  }
  return found;
}
