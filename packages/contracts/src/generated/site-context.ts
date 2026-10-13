/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

/**
 * Everything a site build needs from the engine and an instance, resolved by `pulse site context`: the effective config, the merged sections and item-types registries, locale strings with fallbacks applied, and the schemas reports are validated against. Nested documents are validated against their own schemas when the context is built.
 */
export interface SiteContext {
  schema_version: 1;
  engine_version: string;
  /**
   * Effective configuration (config.schema.json).
   */
  config: {};
  /**
   * Merged sections registry entries (sections.schema.json), sorted by order, then id.
   *
   * @minItems 1
   */
  sections: [{}, ...{}[]];
  /**
   * Merged item-types registry entries (item-types.schema.json).
   *
   * @minItems 1
   */
  item_types: [{}, ...{}[]];
  /**
   * Locale strings for config.language with the fallback chain applied.
   */
  strings: {
    [k: string]: string | undefined;
  };
  /**
   * Schemas keyed by name: report.schema.json (engine) and item-types/<file> for every item type (instance first).
   */
  schemas: {
    [k: string]: {} | undefined;
  };
}
