import type { JsonSchema } from "@pulseai/contracts";

export class SchemaValueError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SchemaValueError";
  }
}

function at(schema: JsonSchema, path: string): unknown {
  let node: unknown = schema;
  for (const key of path.split(".")) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as { [key: string]: unknown })[key];
  }
  return node;
}

/** The `enum` list at a dotted path of a schema: option lists come from schemas, not code. */
export function enumAt(schema: JsonSchema, path: string): string[] {
  const values = at(schema, `${path}.enum`);
  if (!Array.isArray(values) || !values.every((value) => typeof value === "string")) {
    throw new SchemaValueError(`no string enum at ${path}`);
  }
  return values;
}

/** The `required` list at a dotted path (its order is the schema author's field order). */
export function requiredAt(schema: JsonSchema, path: string): string[] {
  const values = at(schema, `${path}.required`);
  if (!Array.isArray(values) || !values.every((value) => typeof value === "string")) {
    throw new SchemaValueError(`no required list at ${path}`);
  }
  return values;
}

/** Every integer from `minimum` to `maximum` at a dotted path. */
export function rangeAt(schema: JsonSchema, path: string): number[] {
  const low = at(schema, `${path}.minimum`);
  const high = at(schema, `${path}.maximum`);
  if (typeof low !== "number" || typeof high !== "number" || low > high) {
    throw new SchemaValueError(`no integer range at ${path}`);
  }
  return Array.from({ length: high - low + 1 }, (_, index) => low + index);
}

/** Report enums the frame renders as options, in schema order. */
export interface ReportEnums {
  confidence: string[];
  ring: string[];
  tier: string[];
  kind: string[];
  theme: string[];
  stats: string[];
  /** Edition modes; the schema lists the regular edition first. */
  edition: string[];
  /** The impact/novelty/relevance scale, lowest first. */
  score: number[];
}

export function reportEnums(report: JsonSchema, config: JsonSchema): ReportEnums {
  return {
    confidence: enumAt(report, "$defs.item.properties.confidence"),
    ring: enumAt(report, "$defs.radarEntry.properties.ring"),
    tier: enumAt(report, "$defs.source.properties.tier"),
    kind: enumAt(report, "$defs.source.properties.kind"),
    theme: enumAt(config, "properties.theme.properties.default"),
    stats: requiredAt(report, "$defs.meta.properties.stats"),
    edition: enumAt(report, "$defs.meta.properties.mode"),
    score: rangeAt(report, "$defs.score"),
  };
}
