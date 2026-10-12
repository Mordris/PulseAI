import type { RenderContext } from "./render.ts";
import type { RunStats, VegaLiteVisual } from "./types.ts";

const VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v6.json";

/**
 * Charts the frame draws from report data (archive heatmap, research funnel, rank changes). They
 * are ordinary vega-lite visuals, themed like every generated chart; labels come from locales.
 */

export interface ArchiveDay {
  date: string;
  score: number;
}

export function archiveHeatmap(days: readonly ArchiveDay[], ctx: RenderContext): VegaLiteVisual {
  const { t } = ctx;
  const cell = ctx.tokenNumber("chart.heatmap_cell");
  return {
    kind: "vega-lite",
    id: "archive-heatmap",
    title: t("ui.archive.heatmap_title"),
    alt: t("ui.archive.heatmap_alt"),
    source_note: t("ui.archive.source"),
    spec: {
      $schema: VEGA_LITE_SCHEMA,
      data: { values: days.map(({ date, score }) => ({ date, score })) },
      // Square day cells, like a contribution calendar.
      width: { step: cell },
      height: { step: cell },
      mark: { type: "rect", cornerRadius: ctx.tokenNumber("chart.bar_corner_radius") },
      encoding: {
        x: {
          field: "date",
          type: "ordinal",
          timeUnit: "yearweek",
          title: null,
          axis: { format: "%b", labelAngle: 0, labelOverlap: "greedy", labelSeparation: 8 },
        },
        y: { field: "date", type: "ordinal", timeUnit: "day", title: null },
        color: { field: "score", type: "quantitative", title: t("ui.score.label") },
        tooltip: [
          { field: "date", type: "temporal", title: t("ui.archive.date") },
          { field: "score", type: "quantitative", title: t("ui.score.label") },
        ],
      },
    },
  };
}

export function researchFunnel(stats: RunStats, ctx: RenderContext): VegaLiteVisual {
  const { t, enums } = ctx;
  const values = enums.stats.map((stage) => ({
    stage: t(`stats.${stage}`),
    count: stats[stage as keyof RunStats],
  }));
  return {
    kind: "vega-lite",
    id: "research-funnel",
    title: t("ui.funnel.title"),
    alt: t(
      "ui.funnel.alt",
      Object.fromEntries(enums.stats.map((stage) => [stage, stats[stage as keyof RunStats]])),
    ),
    source_note: t("ui.funnel.source"),
    spec: {
      $schema: VEGA_LITE_SCHEMA,
      data: { values },
      mark: { type: "bar" },
      encoding: {
        y: { field: "stage", type: "nominal", sort: null, title: null },
        x: { field: "count", type: "quantitative", title: t("ui.funnel.count") },
        tooltip: [
          { field: "stage", type: "nominal", title: t("ui.funnel.stage") },
          { field: "count", type: "quantitative", title: t("ui.funnel.count") },
        ],
      },
    },
  };
}

export interface RankMove {
  name: string;
  before?: number;
  after: number;
}

export function rankChanges(
  id: string,
  title: string,
  movers: readonly RankMove[],
  ctx: RenderContext,
): VegaLiteVisual {
  const { t } = ctx;
  const before = t("fields.before");
  const after = t("fields.after");
  const values = movers.flatMap((move) => [
    ...(move.before === undefined
      ? []
      : [{ name: move.name, when: before, rank: move.before, last: false }]),
    { name: move.name, when: after, rank: move.after, last: true },
  ]);
  return {
    kind: "vega-lite",
    id: `${id}-ranks`,
    title,
    alt: t("ui.leaderboard.alt"),
    source_note: t("ui.leaderboard.source"),
    spec: {
      $schema: VEGA_LITE_SCHEMA,
      data: { values },
      encoding: {
        x: {
          field: "when",
          type: "nominal",
          sort: [before, after],
          title: null,
          axis: { labelAngle: 0 },
        },
        y: {
          field: "rank",
          type: "quantitative",
          scale: { reverse: true, zero: false, nice: false },
          axis: { tickMinStep: 1 },
          title: t("ui.leaderboard.rank_axis"),
        },
      },
      // Series colors mark lines and points only; the direct labels keep the text color.
      layer: [
        {
          mark: { type: "line" },
          encoding: { color: { field: "name", type: "nominal", title: null } },
        },
        {
          mark: { type: "point" },
          encoding: { color: { field: "name", type: "nominal", title: null } },
        },
        {
          transform: [{ filter: { field: "last", equal: true } }],
          mark: { type: "text", align: "left", dx: 8 },
          encoding: { text: { field: "name" } },
        },
      ],
    },
  };
}
