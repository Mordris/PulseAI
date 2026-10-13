import { readFileSync } from "node:fs";
import {
  type ConfigSchema,
  type ItemTypesSchema,
  type JsonSchema,
  type SectionsSchema,
  validator,
} from "@pulseai/contracts";
import { z } from "zod";

export type PulseConfig = ConfigSchema.PulseConfig;
export type Section = SectionsSchema.Section;
export type SectionGroup = SectionsSchema.SectionGroup;
export type ItemType = ItemTypesSchema.ItemType;

/** The bundle `pulse site context` writes (schema/site-context.schema.json), with typed parts. */
export interface SiteContext {
  schema_version: 1;
  engine_version: string;
  config: PulseConfig;
  sections: Section[];
  item_types: ItemType[];
  strings: { [key: string]: string };
  schemas: { [name: string]: JsonSchema };
}

export class SiteContextError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SiteContextError";
  }
}

/** Validate a parsed context: the bundle shape, then each nested document with its own schema. */
export function parseSiteContext(data: unknown, source: string): SiteContext {
  const bundle = validator("site-context").safeParse(data);
  if (!bundle.success) {
    throw new SiteContextError(`${source}: not a site context\n${z.prettifyError(bundle.error)}`);
  }
  const doc = data as SiteContext;
  const parts: [string, string, unknown][] = [
    ["config", "config", doc.config],
    ["sections", "sections", { schema_version: 1, sections: doc.sections }],
    ["item_types", "item-types", { schema_version: 1, item_types: doc.item_types }],
  ];
  for (const [field, schema, value] of parts) {
    const result = validator(schema).safeParse(value);
    if (!result.success) {
      throw new SiteContextError(
        `${source}: ${field} is invalid\n${z.prettifyError(result.error)}`,
      );
    }
  }
  return doc;
}

export function loadSiteContext(file: string): SiteContext {
  let text: string;
  try {
    text = readFileSync(file, "utf8");
  } catch {
    throw new SiteContextError(
      `${file}: not found; run "pulse site context --instance <dir>" before building the site`,
    );
  }
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (error) {
    throw new SiteContextError(`${file}: ${(error as Error).message}`);
  }
  return parseSiteContext(data, file);
}
