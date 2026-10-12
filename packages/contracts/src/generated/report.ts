/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

/**
 * RFC 3339 timestamp. The pattern requires an uppercase T and Z, which is all Zod accepts, so Python and TypeScript agree.
 */
export type DateTime = string;
export type Id = string;
export type ShortText = string;
export type Slug = string;
export type Visual =
  VegaLiteVisual | MermaidVisual | TableVisual | ImageRefVisual | DashboardVisual;
export type Alt = string;
export type HttpUrl = string;
export type DashboardTile = StatTile | VisualTile;
export type Span = number;
/**
 * A visual that can sit inside a dashboard tile (any kind except dashboard).
 */
export type LeafVisual = VegaLiteVisual | MermaidVisual | TableVisual | ImageRefVisual;
export type Score = number;
export type Text = string;

/**
 * One daily PulseAI report (report.json). Each item's detail object is validated separately with the schema named by its item type.
 */
export interface Report {
  schema_version: 1;
  meta: ReportMeta;
  headline: ShortText;
  pulse_score: PulseScore;
  kpis: Kpi[];
  tldr: TldrLine[];
  featured: {
    [k: string]: Slug | undefined;
  };
  front_page: Visual[];
  items: Item[];
  adoption_radar: RadarEntry[];
  action_list: ActionItem[];
  signals: Item[];
  corrections: Correction[];
  section_notes: {
    [k: string]: SectionNote[] | undefined;
  };
  methodology: Methodology;
}
export interface ReportMeta {
  date: string;
  edition: number;
  window: ReportWindow;
  language: string;
  engine_version: string;
  host: "routine" | "actions" | "local" | "fixture";
  models: {
    [k: string]: string | undefined;
  };
  stats: RunStats;
  cost_usd: number | null;
  source_health: SourceHealth[];
  sample: boolean;
  mode: "normal" | "plain" | "catch_up";
}
export interface ReportWindow {
  start: DateTime;
  end: DateTime;
  tz: string;
}
export interface RunStats {
  scanned: number;
  triaged: number;
  verified: number;
  published: number;
}
export interface SourceHealth {
  source_id: Id;
  ok: boolean;
  items: number;
  error?: string;
}
export interface PulseScore {
  value: number;
  avg_7d: number | null;
}
export interface Kpi {
  label: ShortText;
  value: string | number;
  delta?: number;
  series?: number[];
}
export interface TldrLine {
  text: ShortText;
  item_id: Slug;
}
export interface VegaLiteVisual {
  kind: "vega-lite";
  id: Slug;
  title: ShortText;
  alt: Alt;
  source_note: ShortText;
  /**
   * Deep-dive block of the item's type to render this visual in. Without it the visual renders after the item's facts.
   */
  block?: string;
  spec: {};
}
export interface MermaidVisual {
  kind: "mermaid";
  id: Slug;
  title: ShortText;
  alt: Alt;
  source_note: ShortText;
  /**
   * Deep-dive block of the item's type to render this visual in. Without it the visual renders after the item's facts.
   */
  block?: string;
  code: string;
}
export interface TableVisual {
  kind: "table";
  id: Slug;
  title: ShortText;
  alt: Alt;
  source_note: ShortText;
  /**
   * Deep-dive block of the item's type to render this visual in. Without it the visual renders after the item's facts.
   */
  block?: string;
  /**
   * @minItems 1
   */
  columns: [ShortText, ...ShortText[]];
  rows: (string | number | boolean | null)[][];
}
export interface ImageRefVisual {
  kind: "image-ref";
  id: Slug;
  title: ShortText;
  alt: Alt;
  source_note: ShortText;
  /**
   * Deep-dive block of the item's type to render this visual in. Without it the visual renders after the item's facts.
   */
  block?: string;
  image: ItemImage;
}
export interface ItemImage {
  url: HttpUrl;
  caption: ShortText;
  credit: ShortText;
  alt: Alt;
  license?: string;
}
export interface DashboardVisual {
  kind: "dashboard";
  id: Slug;
  title: ShortText;
  alt: Alt;
  source_note: ShortText;
  /**
   * Deep-dive block of the item's type to render this visual in. Without it the visual renders after the item's facts.
   */
  block?: string;
  columns: number;
  /**
   * @minItems 1
   * @maxItems 12
   */
  tiles:
    | [DashboardTile]
    | [DashboardTile, DashboardTile]
    | [DashboardTile, DashboardTile, DashboardTile]
    | [DashboardTile, DashboardTile, DashboardTile, DashboardTile]
    | [DashboardTile, DashboardTile, DashboardTile, DashboardTile, DashboardTile]
    | [DashboardTile, DashboardTile, DashboardTile, DashboardTile, DashboardTile, DashboardTile]
    | [
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile
      ]
    | [
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile
      ]
    | [
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile
      ]
    | [
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile
      ]
    | [
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile
      ]
    | [
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile,
        DashboardTile
      ];
}
export interface StatTile {
  tile: "stat";
  span?: Span;
  label: ShortText;
  value: string | number;
  unit?: string;
  delta?: number;
  series?: number[];
}
export interface VisualTile {
  tile: "visual";
  span?: Span;
  visual: LeafVisual;
}
export interface Item {
  id: Slug;
  section: Id;
  type: Id;
  title: ShortText;
  entity_key: string;
  thread_id?: Slug;
  update_of?: string;
  impact: Score;
  novelty: Score;
  relevance: Score;
  confidence: "confirmed" | "reported" | "rumor";
  summary: Text;
  why_it_matters: Text;
  what_to_do?: Text;
  caveats?: Text;
  /**
   * @minItems 1
   */
  sources: [ItemSource, ...ItemSource[]];
  facts: ItemFact[];
  visuals: Visual[];
  images: ItemImage[];
  detail: {};
}
export interface ItemSource {
  url: HttpUrl;
  title: ShortText;
  tier: "T1" | "T1-data" | "T2" | "T3";
  kind: "primary" | "secondary";
  fetched_at?: DateTime;
}
export interface ItemFact {
  label: ShortText;
  value: string | number;
  unit?: string;
  source_ref: number;
  quote: string;
}
export interface RadarEntry {
  item_id: Slug;
  ring: "adopt" | "trial" | "assess" | "hold";
  rationale: Text;
}
export interface ActionItem {
  text: ShortText;
  item_id?: Slug;
}
export interface Correction {
  report_date: string;
  item_id: Slug;
  text: Text;
}
export interface SectionNote {
  group?: Id;
  title: ShortText;
  text: Text;
  url?: HttpUrl;
}
export interface Methodology {
  notes: Text[];
  rejected: RejectedItem[];
}
export interface RejectedItem {
  title: ShortText;
  reason: ShortText;
  url?: HttpUrl;
}
