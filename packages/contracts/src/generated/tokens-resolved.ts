/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Id = string;
export type Path = string;

/**
 * Design tokens for one theme mode after layering (engine, preset, instance, config overrides) and alias resolution. Written by @pulseai/tokens; read by the site and by `pulse tokens check`.
 */
export interface ResolvedTokens {
  schema_version: 1;
  preset: Id;
  mode: "light" | "dark";
  tokens: {
    [k: string]: ResolvedToken | undefined;
  };
}
export interface ResolvedToken {
  value: string | number;
  type: string;
  name: string;
  extensions?: TokenExtensions;
}
/**
 * The org.pulseai entry of a token's $extensions.
 */
export interface TokenExtensions {
  /**
   * Surface tokens this (text) color must reach quality.text_contrast_min against.
   *
   * @minItems 1
   */
  contrast_against?: [Path, ...Path[]];
  distinct?: DistinctMember;
  /**
   * Key of config.theme.overrides that replaces this token's value.
   */
  override?: string;
  /**
   * Fontsource package that provides this font family.
   */
  fontsource?: string;
}
/**
 * Membership in a set of colors that must stay distinguishable. With order on every member, only neighbours are compared (categorical chart order); otherwise every pair is.
 */
export interface DistinctMember {
  set: Id;
  order?: number;
}
