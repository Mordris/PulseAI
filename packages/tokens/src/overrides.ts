import type { ConfigSchema } from "@pulseai/contracts";
import { TokenError, type TokenTree } from "./layers.ts";

export const EXTENSION = "org.pulseai";

/** config.theme.overrides, typed from schema/config.schema.json. */
export type ThemeOverrides = ConfigSchema.ThemeOverrides;

/** The part of a sections registry entry the token build needs. */
export interface SectionColor {
  id: string;
  color_token: string;
}

export interface TokenLeaf {
  path: string[];
  token: TokenTree;
}

/** Every token (an object with `$value`) in a tree, with its path. */
export function leaves(tree: TokenTree, path: string[] = []): TokenLeaf[] {
  const found: TokenLeaf[] = [];
  for (const [key, value] of Object.entries(tree)) {
    if (
      key.startsWith("$") ||
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value)
    ) {
      continue;
    }
    const child = value as TokenTree;
    if ("$value" in child) {
      found.push({ path: [...path, key], token: child });
    } else {
      found.push(...leaves(child, [...path, key]));
    }
  }
  return found;
}

/** The org.pulseai entry of a token's $extensions, if any. */
export function extensionOf(token: TokenTree): TokenTree | undefined {
  const extensions = token.$extensions;
  if (extensions === null || typeof extensions !== "object") return undefined;
  const entry = (extensions as TokenTree)[EXTENSION];
  return entry !== null && typeof entry === "object" ? (entry as TokenTree) : undefined;
}

/** The token at a dotted path, if the tree defines one. */
export function findToken(tree: TokenTree, path: string): TokenTree | undefined {
  let node: unknown = tree;
  for (const key of path.split(".")) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as TokenTree)[key];
  }
  return node !== null && typeof node === "object" && "$value" in node
    ? (node as TokenTree)
    : undefined;
}

/**
 * Apply config.theme.overrides to a copy of the tree. A string override replaces every token
 * whose extension names its key; `sections` replaces each listed section's color token.
 */
export function applyOverrides(
  tree: TokenTree,
  overrides: ThemeOverrides,
  sections: readonly SectionColor[],
): TokenTree {
  const result = structuredClone(tree);
  const keyed = overrides as { [key: string]: unknown };
  for (const { token } of leaves(result)) {
    const extension = extensionOf(token);
    const key = extension?.override;
    if (typeof key !== "string") continue;
    const value = keyed[key];
    if (value === undefined) continue;
    if (typeof value !== "string") {
      throw new TokenError(`theme.overrides.${key} must be a string`);
    }
    if (Array.isArray(token.$value)) {
      // A font override keeps the token's fallbacks; the new family is not a Fontsource package.
      token.$value = [value, ...token.$value.slice(1)];
      delete extension?.fontsource;
    } else {
      token.$value = value;
    }
  }
  for (const [sectionId, color] of Object.entries(overrides.sections ?? {})) {
    if (color === undefined) continue;
    const section = sections.find((candidate) => candidate.id === sectionId);
    if (section === undefined) {
      throw new TokenError(`theme.overrides.sections names unknown section "${sectionId}"`);
    }
    const token = findToken(result, section.color_token);
    if (token === undefined) {
      throw new TokenError(missingSectionToken(section));
    }
    token.$value = color;
  }
  return result;
}

export function missingSectionToken(section: SectionColor): string {
  return `section "${section.id}" uses color token "${section.color_token}", which no token file defines`;
}
