import { MODES, type Mode, type ResolvedTokens, token } from "@pulseai/tokens";

/** Prefix of the categorical chart palette; slots are numbered from 1 in token order. */
const CATEGORY_PREFIX = "color.chart.category.";

/** Chart and diagram themes for both modes, built from resolved tokens and inlined in each page. */
export interface ThemeData {
  vega: Record<Mode, VegaConfig>;
  mermaid: Record<Mode, MermaidVariables>;
}

export type VegaConfig = { [key: string]: unknown };
export interface MermaidVariables {
  fontFamily: string;
  [key: string]: string;
}

function text(tokens: ResolvedTokens, path: string): string {
  return String(token(tokens, path).value);
}

function num(tokens: ResolvedTokens, path: string): number {
  const value = token(tokens, path).value;
  const parsed = typeof value === "number" ? value : Number.parseFloat(value);
  if (Number.isNaN(parsed)) throw new Error(`token "${path}" is not a number`);
  return parsed;
}

/** The categorical palette in slot order. */
export function categoryColors(tokens: ResolvedTokens): string[] {
  return Object.keys(tokens.tokens)
    .filter((path) => path.startsWith(CATEGORY_PREFIX))
    .sort(
      (a, b) => Number(a.slice(CATEGORY_PREFIX.length)) - Number(b.slice(CATEGORY_PREFIX.length)),
    )
    .map((path) => text(tokens, path));
}

/** A Vega-Lite config: chrome, palette, and mark defaults from tokens; reports never set colors. */
export function vegaConfig(tokens: ResolvedTokens): VegaConfig {
  const font = text(tokens, "font.family.body");
  const label = text(tokens, "color.chart.label");
  const axis = text(tokens, "color.chart.axis");
  const labelSize = num(tokens, "chart.label_size");
  const category = categoryColors(tokens);
  const ramp = [text(tokens, "color.chart.ramp.low"), text(tokens, "color.chart.ramp.high")];
  return {
    background: "transparent",
    font,
    padding: 4,
    view: { stroke: "transparent", continuousHeight: num(tokens, "chart.height") },
    axis: {
      domainColor: axis,
      tickColor: axis,
      gridColor: text(tokens, "color.chart.grid"),
      labelColor: label,
      titleColor: label,
      labelFont: font,
      titleFont: font,
      labelFontSize: labelSize,
      titleFontSize: labelSize,
      titleFontWeight: num(tokens, "font.weight.medium"),
    },
    // Horizontal category labels read best; Vega-Lite drops overlapping ones.
    axisX: { labelAngle: 0, labelOverlap: true },
    legend: {
      labelColor: label,
      titleColor: label,
      labelFont: font,
      titleFont: font,
      labelFontSize: labelSize,
      titleFontSize: labelSize,
    },
    header: { labelColor: label, titleColor: label, labelFont: font, titleFont: font },
    title: {
      color: text(tokens, "color.text.primary"),
      font,
      fontSize: num(tokens, "chart.title_size"),
    },
    range: { category, ramp, heatmap: ramp, ordinal: ramp },
    mark: { color: category[0] },
    bar: { cornerRadiusEnd: num(tokens, "chart.bar_corner_radius") },
    line: { strokeWidth: num(tokens, "chart.line_width") },
    point: { size: num(tokens, "chart.point_size"), filled: true },
    rule: { color: axis },
    text: { color: text(tokens, "color.text.secondary"), font, fontSize: labelSize },
  };
}

/** Mermaid "base" theme variables from tokens. */
export function mermaidVariables(tokens: ResolvedTokens): MermaidVariables {
  const raised = text(tokens, "color.surface.raised");
  const sunken = text(tokens, "color.surface.sunken");
  const primary = text(tokens, "color.text.primary");
  return {
    fontFamily: text(tokens, "font.family.body"),
    background: raised,
    mainBkg: sunken,
    primaryColor: sunken,
    primaryTextColor: primary,
    primaryBorderColor: text(tokens, "color.accent.default"),
    secondaryColor: raised,
    tertiaryColor: text(tokens, "color.surface.page"),
    textColor: primary,
    titleColor: primary,
    lineColor: text(tokens, "color.text.secondary"),
    nodeBorder: text(tokens, "color.border.strong"),
    clusterBkg: text(tokens, "color.surface.page"),
    clusterBorder: text(tokens, "color.border.subtle"),
    edgeLabelBackground: raised,
    noteBkgColor: sunken,
    noteTextColor: primary,
  };
}

export function themeData(tokens: Record<Mode, ResolvedTokens>): ThemeData {
  const vega = {} as Record<Mode, VegaConfig>;
  const mermaid = {} as Record<Mode, MermaidVariables>;
  for (const mode of MODES) {
    vega[mode] = vegaConfig(tokens[mode]);
    mermaid[mode] = mermaidVariables(tokens[mode]);
  }
  return { vega, mermaid };
}
