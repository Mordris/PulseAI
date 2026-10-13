/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export interface ArticleDetail {
  author: string;
  publication: string;
  /**
   * @minItems 1
   */
  key_points: [string, ...string[]];
  reading_minutes: number;
  worth_full_read: boolean;
  worth_reason: string;
}
