/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

/**
 * RFC 3339 timestamp. The pattern requires an uppercase T and Z, which is all Zod accepts, so Python and TypeScript agree.
 */
export type Timestamp = string;
export type Id = string;
export type Ids = Id[];
/**
 * One source's result. ok and empty rows have no reason; failed and skipped rows must give one. items counts the items written to the source's file, and unread the sitemap candidates left unread past meta_fetch_limit.
 */
export type SourceOutcome = SucceededOutcome | FailedOutcome;
/**
 * @minItems 1
 */
export type SectionIds = [Id, ...Id[]];
export type CollectorKind = "rss" | "atom" | "json" | "json-snapshot-diff" | "sitemap";
/**
 * The final response status, or null when no response was received.
 */
export type HttpStatus = number | null;
export type Count = number;
/**
 * The host a redirect ended on when it differs from the requested one, otherwise null.
 */
export type RedirectHost = string | null;
export type Reason =
  | "http_error"
  | "timeout"
  | "network_error"
  | "rate_limited"
  | "robots_disallowed"
  | "missing_auth_env"
  | "parse_error"
  | "invalid_items"
  | "too_large"
  | "offline_miss";

/**
 * The outcome of one pulse collect run, one row per selected source (runs/<date>/collected/collect.json). A partial re-run keeps the other sources' rows and refreshes updated_at.
 */
export interface CollectRun {
  schema_version: 1;
  engine_version: string;
  run_date: string;
  started_at: Timestamp;
  updated_at: Timestamp;
  window: RunWindow;
  options: RunOptions;
  sources: SourceOutcome[];
  /**
   * Enabled sources that pulse collect does not read (via mcp or search), listed so the researchers handle them.
   */
  not_collected: NotCollected[];
}
/**
 * The collection window: items published in [since, until) were kept.
 */
export interface RunWindow {
  since: Timestamp;
  until: Timestamp;
}
/**
 * The command-line choices for this run. Empty lists mean no filter.
 */
export interface RunOptions {
  sections: Ids;
  sources: Ids;
  offline: boolean;
}
/**
 * A source that was read: ok, or empty when nothing was left after filtering.
 */
export interface SucceededOutcome {
  id: Id;
  status: "ok" | "empty";
  sections: SectionIds;
  kind: CollectorKind;
  http_status: HttpStatus;
  items: Count;
  items_dropped_window: Count;
  items_dropped_invalid: Count;
  duration_ms: Count;
  from_cache: boolean;
  redirected_to: RedirectHost;
  note: string | null;
  unread: Count;
}
/**
 * A source with no usable result: failed while reading, or skipped before any request.
 */
export interface FailedOutcome {
  id: Id;
  status: "failed" | "skipped";
  reason: Reason;
  sections: SectionIds;
  kind: CollectorKind;
  http_status: HttpStatus;
  items: Count;
  items_dropped_window: Count;
  items_dropped_invalid: Count;
  duration_ms: Count;
  from_cache: boolean;
  redirected_to: RedirectHost;
  note: string | null;
  unread: Count;
}
export interface NotCollected {
  id: Id;
  via: "mcp" | "search";
  sections: SectionIds;
}
