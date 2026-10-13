/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Id = string;
export type LocaleKey = string;
export type Field = string;

/**
 * Item types (taxonomy/item-types.yaml). Each type's detail object is validated by its schema in schema/item-types/.
 */
export interface ItemTypesRegistry {
  schema_version: 1;
  /**
   * @minItems 1
   */
  item_types: [ItemType, ...ItemType[]];
}
export interface ItemType {
  id: Id;
  label: LocaleKey;
  schema: string;
  component: string;
  /**
   * @minItems 1
   */
  blocks: [Id, ...Id[]];
  brief_fields: Field[];
  markdown_fields: Field[];
}
