/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Source = CollectorSource | McpSource | SearchSource;
export type Id = string;
export type Text = string;
export type Url = string;
export type Tier = "T1" | "T1-data" | "T2" | "T3";
/**
 * @minItems 1
 */
export type SectionIds = [Id, ...Id[]];
export type Trust = number;
export type Collector = FeedCollector | JsonCollector | SnapshotCollector | SitemapCollector;
export type UrlTemplate = string;
export type Jmespath = string;
export type EnvName = string;
export type PathGlob = string;

/**
 * Research sources (sources/registry/*.yaml). Each source is read by the generic collector, an MCP tool, or web search.
 */
export interface SourcesRegistry {
  schema_version: 1;
  sources: Source[];
}
export interface CollectorSource {
  id: Id;
  name: Text;
  homepage?: Url;
  tier: Tier;
  sections: SectionIds;
  trust: Trust;
  enabled: boolean;
  notes?: string;
  /**
   * Keep undated items (the source is a changelog or release list). Default false.
   */
  changelog?: boolean;
  via: "collector";
  collector: Collector;
}
export interface FeedCollector {
  kind: "rss" | "atom";
  url: UrlTemplate;
  fields?: FieldMap;
  http?: HttpOptions;
}
export interface FieldMap {
  id?: Jmespath;
  title: Jmespath;
  url: Jmespath;
  published?: Jmespath;
  summary?: Jmespath;
  signal?: Jmespath;
  /**
   * More values to keep on each item, as output key to JMESPath.
   */
  extra?: {
    [k: string]: Jmespath | undefined;
  };
}
export interface HttpOptions {
  auth_header?: string;
  auth_env?: EnvName;
  auth_prefix?: string;
  /**
   * Send the request without auth when auth_env is unset, instead of failing. Default false.
   */
  auth_optional?: boolean;
  timeout_seconds?: number;
  rate_limit_per_minute?: number;
  retries?: number;
}
export interface JsonCollector {
  kind: "json";
  url: UrlTemplate;
  items: Jmespath;
  fields: FieldMap;
  http?: HttpOptions;
}
export interface SnapshotCollector {
  kind: "json-snapshot-diff";
  url: UrlTemplate;
  items: Jmespath;
  key: Jmespath;
  track?: Jmespath[];
  fields: FieldMap;
  http?: HttpOptions;
}
export interface SitemapCollector {
  kind: "sitemap";
  url: UrlTemplate;
  /**
   * URL path globs to keep, each starting with /.
   *
   * @minItems 1
   */
  include: [PathGlob, ...PathGlob[]];
  /**
   * URL path globs to drop from the included set.
   *
   * @minItems 1
   */
  exclude?: [PathGlob, ...PathGlob[]];
  /**
   * Most pages read per run; defaults to collect.meta_fetch_limit.
   */
  meta_fetch_limit?: number;
  http?: HttpOptions;
}
export interface McpSource {
  id: Id;
  name: Text;
  homepage?: Url;
  tier: Tier;
  sections: SectionIds;
  trust: Trust;
  enabled: boolean;
  notes?: string;
  via: "mcp";
  mcp: McpCall;
}
export interface McpCall {
  server: Id;
  tool: string;
  args?: {};
}
export interface SearchSource {
  id: Id;
  name: Text;
  homepage?: Url;
  tier: Tier;
  sections: SectionIds;
  trust: Trust;
  enabled: boolean;
  notes?: string;
  via: "search";
  search: SearchSpec;
}
export interface SearchSpec {
  /**
   * @minItems 1
   */
  queries: [Text, ...Text[]];
  domains?: string[];
  /**
   * Pages an agent should fetch and read directly, for labs with neither a feed nor a sitemap.
   */
  pages?: Url[];
}
