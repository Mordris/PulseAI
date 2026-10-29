/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Id = string;
/**
 * @minItems 1
 */
export type SectionIds = [Id, ...Id[]];
/**
 * RFC 3339 timestamp. The pattern requires an uppercase T and Z, which is all Zod accepts, so Python and TypeScript agree.
 */
export type Timestamp = string;
/**
 * One item. A dated item carries its publication time; an undated one (a changelog entry, a snapshot change) has undated true and published null.
 */
export type CollectedItem = DatedItem | UndatedItem;
/**
 * <source-id>:<slug or hash of the canonical URL>, stable across runs.
 */
export type ItemId = string;
export type HttpsUrl = string;
export type Scalar = string | number | boolean | null;

/**
 * What pulse collect read from one source (runs/<date>/collected/<source-id>.json).
 */
export interface CollectedSource {
  schema_version: 1;
  source: SourceInfo;
  window: TimeWindow;
  collected_at: Timestamp;
  items: CollectedItem[];
}
/**
 * The registry entry this file was collected from.
 */
export interface SourceInfo {
  id: Id;
  name: string;
  tier: "T1" | "T1-data" | "T2" | "T3";
  trust: number;
  sections: SectionIds;
  kind: "rss" | "atom" | "json" | "json-snapshot-diff" | "sitemap";
  /**
   * The URL that was fetched, with its template variables expanded.
   */
  url: string;
}
/**
 * The collection window: items published in [since, until) were kept.
 */
export interface TimeWindow {
  since: Timestamp;
  until: Timestamp;
}
export interface DatedItem {
  id: ItemId;
  source_id: Id;
  title: string;
  url: HttpsUrl;
  canonical_url: HttpsUrl;
  published: Timestamp;
  undated: false;
  summary: string | null;
  signal: number | null;
  extra: Extra;
  detected_at?: Timestamp;
  change?: ItemChange;
}
/**
 * Values the registry's fields.extra map picked from the entry, by output key.
 */
export interface Extra {
  [k: string]: Scalar | undefined;
}
/**
 * What changed since the earlier snapshot (json-snapshot-diff and sitemap sources).
 */
export interface ItemChange {
  kind: "added" | "removed" | "changed" | "updated";
  fields: FieldChange[];
}
export interface FieldChange {
  path: string;
  old: unknown;
  new: unknown;
}
export interface UndatedItem {
  id: ItemId;
  source_id: Id;
  title: string;
  url: HttpsUrl;
  canonical_url: HttpsUrl;
  published: null;
  undated: true;
  summary: string | null;
  signal: number | null;
  extra: Extra;
  detected_at?: Timestamp;
  change?: ItemChange;
}
