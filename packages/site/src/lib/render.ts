import { getSchema, type JsonSchema } from "@pulseai/contracts";
import { type Mode, type ResolvedTokens, token } from "@pulseai/tokens";
import type { ItemType, PulseConfig, Section, SiteContext } from "./context.ts";
import { createFormatters, type Formatters } from "./format.ts";
import { createTranslator, type Translator } from "./i18n.ts";
import { type ReportEnums, reportEnums } from "./schema-values.ts";

const REPORT_SCHEMA = "report.schema.json";
const ITEM_TYPE_SCHEMA_DIR = "item-types";

/** What every component needs to render: strings, formats, registries, tokens, and links. */
export interface RenderContext {
  t: Translator;
  fmt: Formatters;
  lang: string;
  engineVersion: string;
  config: PulseConfig;
  /** Sections in registry order. */
  sections: readonly Section[];
  section(id: string): Section | undefined;
  itemType(id: string): ItemType | undefined;
  /** The detail schema of an item type, as the context resolved it. */
  detailSchema(itemType: ItemType): JsonSchema;
  minImpact: number;
  enums: ReportEnums;
  /** `var(--pulse-…)` for a token path; throws when no theme defines it. */
  cssVar(path: string): string;
  /** A numeric token (chart sizes); throws when it is missing or not a number. */
  tokenNumber(path: string): number;
  /** A link below the site's base path: url("2026/10/11/") -> "/PulseAI/2026/10/11/". */
  url(path: string): string;
  /** A page's <title>: the page name and the site name, joined by the locale's template. */
  pageTitle(page: string): string;
}

export class RenderContextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RenderContextError";
  }
}

export function createRenderContext(
  context: SiteContext,
  tokens: Record<Mode, ResolvedTokens>,
  base: string,
): RenderContext {
  const lang = context.config.language;
  const sections = new Map(context.sections.map((section) => [section.id, section]));
  const itemTypes = new Map(context.item_types.map((itemType) => [itemType.id, itemType]));
  const schema = (name: string): JsonSchema => {
    const found = context.schemas[name];
    if (found === undefined) throw new RenderContextError(`the site context has no ${name}`);
    return found;
  };
  const t = createTranslator(context.strings, lang);
  return {
    t,
    fmt: createFormatters(lang),
    lang,
    engineVersion: context.engine_version,
    config: context.config,
    sections: context.sections,
    section: (id) => sections.get(id),
    itemType: (id) => itemTypes.get(id),
    detailSchema: (itemType) => schema(`${ITEM_TYPE_SCHEMA_DIR}/${itemType.schema}`),
    minImpact: context.config.deep_dive.min_impact,
    // The theme choices are an engine contract (config.schema.json ships with @pulseai/contracts).
    enums: reportEnums(schema(REPORT_SCHEMA), getSchema("config")),
    cssVar: (path) => `var(${token(tokens.light, path).name})`,
    tokenNumber: (path) => {
      const value = token(tokens.light, path).value;
      if (typeof value !== "number")
        throw new RenderContextError(`token "${path}" is not a number`);
      return value;
    },
    url: (path) => `${base}${path.replace(/^\/+/, "")}`,
    pageTitle: (page) => t("ui.page.title", { page, site: t("ui.site.title") }),
  };
}
