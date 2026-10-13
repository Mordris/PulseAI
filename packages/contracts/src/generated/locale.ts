/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

/**
 * UI strings for one language (locales/<language>.json).
 */
export interface Locale {
  schema_version: 1;
  language: string;
  fallback: string | null;
  strings: {
    [k: string]: string | undefined;
  };
}
