/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Language = string;
export type Terms = string[];
export type Score = number;
export type Id = string;
export type Hex = string;
export type Font = string;
export type Ids = Id[];
export type EnvName = string;

/**
 * Effective configuration: defaults/pulse.config.yaml merged with the instance pulse.config.yaml and PULSE__ environment overrides.
 */
export interface PulseConfig {
  engine: EngineConfig;
  schedule: ScheduleConfig;
  language: Language;
  interests: InterestsConfig;
  sections: {
    [k: string]: SectionToggle | undefined;
  };
  deep_dive: DeepDiveConfig;
  confidence: ConfidenceConfig;
  window: WindowConfig;
  collect: CollectConfig;
  models_by_role: {
    [k: string]: string | undefined;
  };
  limits: LimitsConfig;
  quality: QualityConfig;
  theme: ThemeConfig;
  visuals: VisualsConfig;
  mcp: McpConfig;
  site: SiteConfig;
  publish: PublishConfig;
  notify: NotifyConfig;
  telemetry: TelemetryConfig;
}
export interface EngineConfig {
  /**
   * Engine release (semver) or git ref.
   */
  version: string;
}
export interface ScheduleConfig {
  /**
   * Local start time, 24-hour HH:MM.
   */
  time: string;
  /**
   * IANA time zone, e.g. Europe/Istanbul.
   */
  tz: string;
  /**
   * Cloud schedulers start late on the hour; shift on-the-hour times by this many minutes.
   */
  cloud_offset_minutes_when_on_hour: number;
}
export interface InterestsConfig {
  high: Terms;
  normal: Terms;
}
export interface SectionToggle {
  enabled: boolean;
  max_items: number;
  options?: {};
}
export interface DeepDiveConfig {
  min_impact: Score;
}
export interface ConfidenceConfig {
  reported: "main" | "signals_box" | "exclude";
  rumor: "signals_box" | "exclude";
}
export interface WindowConfig {
  max_hours: number;
}
/**
 * Defaults for pulse collect. A source's own http block overrides the HTTP settings.
 */
export interface CollectConfig {
  /**
   * User-Agent template in printable ASCII; {version} becomes the engine version.
   */
  user_agent: string;
  /**
   * Most sources fetched at the same time.
   */
  concurrency: number;
  /**
   * Requests per minute to one host, unless a source sets a lower rate_limit_per_minute.
   */
  per_host_per_minute: number;
  /**
   * Request timeout.
   */
  timeout_seconds: number;
  /**
   * Retries after a network error, 429 or 5xx.
   */
  retries: number;
  /**
   * Longest Retry-After or rate-limit reset worth waiting for; a longer wait fails the source.
   */
  max_wait_seconds: number;
  /**
   * Most redirects followed per request.
   */
  max_redirects: number;
  /**
   * Largest response body read; a bigger one fails the source.
   */
  max_response_bytes: number;
  /**
   * Item summaries are cut to this many characters.
   */
  summary_max_chars: number;
  /**
   * Item titles are cut to this many characters.
   */
  title_max_chars: number;
  /**
   * Check robots.txt before fetching a page.
   */
  respect_robots: boolean;
  /**
   * HTTP cache directory, relative to the instance.
   */
  cache_dir: string;
  /**
   * Dated snapshots kept per source. Two are needed so that re-running a date still has the earlier snapshot to compare with.
   */
  snapshot_keep: number;
  /**
   * Default for the most pages a sitemap source reads per run.
   */
  meta_fetch_limit: number;
  /**
   * Most child sitemaps followed from a sitemap index.
   */
  max_child_sitemaps: number;
}
export interface LimitsConfig {
  run_minutes: number;
  max_budget_usd: number;
  design_fix_rounds: number;
  agent_max_turns: number;
}
export interface QualityConfig {
  text_contrast_min: number;
  section_delta_e_min: number;
  section_cvd_fail: number;
  section_cvd_target: number;
  design_review_min_score: number;
  /**
   * Source tiers that count as primary evidence for a confirmed item.
   *
   * @minItems 1
   */
  primary_tiers: ["T1" | "T1-data" | "T2" | "T3", ...("T1" | "T1-data" | "T2" | "T3")[]];
  /**
   * Color-vision-deficiency simulations applied to distinct color sets (ColorAide filter names).
   *
   * @minItems 1
   */
  cvd_simulations: ["protan" | "deutan" | "tritan", ...("protan" | "deutan" | "tritan")[]];
}
export interface ThemeConfig {
  default: "auto" | "light" | "dark";
  switcher: boolean;
  preset: Id;
  overrides: ThemeOverrides;
}
export interface ThemeOverrides {
  accent?: Hex;
  font_display?: Font;
  font_body?: Font;
  sections?: {
    [k: string]: Hex | undefined;
  };
}
export interface VisualsConfig {
  min_per_deep_dive: number;
  motion: boolean;
  notify_media: "png" | "gif" | "none";
}
export interface McpConfig {
  enabled: Ids;
  optional: Ids;
}
export interface SiteConfig {
  url: string | null;
  search: boolean;
  /**
   * How many of the newest editions the RSS feed lists.
   */
  feed_items: number;
}
export interface PublishConfig {
  repo: string | null;
  branch: string;
}
export interface NotifyConfig {
  urls_env: EnvName;
  on_failure: boolean;
}
export interface TelemetryConfig {
  otel_endpoint_env: EnvName;
}
