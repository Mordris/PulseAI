/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Id = string;
export type LocaleKey = string;

/**
 * Report sections (taxonomy/sections.yaml).
 */
export interface SectionsRegistry {
  schema_version: 1;
  /**
   * @minItems 1
   */
  sections: [Section, ...Section[]];
}
export interface Section {
  id: Id;
  label: LocaleKey;
  color_token: string;
  order: number;
  /**
   * Impact definitions for scores 1 to 5, in order.
   *
   * @minItems 5
   * @maxItems 5
   */
  rubric: [string, string, string, string, string];
  /**
   * @minItems 1
   */
  default_item_types: [Id, ...Id[]];
  researcher_brief: string;
  groups: SectionGroup[];
}
export interface SectionGroup {
  id: Id;
  label: LocaleKey;
  match: GroupMatch;
}
export interface GroupMatch {
  featured?: Id;
  /**
   * @minItems 1
   */
  types?: [Id, ...Id[]];
  depth?: "deep" | "brief";
}
