import type { Section, SectionGroup } from "./context.ts";
import type { Item, LeafVisual, Report, Visual } from "./types.ts";

export type Depth = "deep" | "brief";

/** Items below deep_dive.min_impact render as compact briefs. */
export function itemDepth(item: Item, minImpact: number): Depth {
  return item.impact >= minImpact ? "deep" : "brief";
}

/** Every condition a group's match names must hold. */
export function matchesGroup(
  item: Item,
  group: SectionGroup,
  featured: Report["featured"],
  minImpact: number,
): boolean {
  const { match } = group;
  if (match.featured !== undefined && featured[match.featured] !== item.id) return false;
  if (match.types !== undefined && !match.types.includes(item.type)) return false;
  if (match.depth !== undefined && itemDepth(item, minImpact) !== match.depth) return false;
  return true;
}

export interface ItemGroup {
  /** The registry group, or undefined for items no group matched. */
  group: SectionGroup | undefined;
  items: Item[];
}

/**
 * A section's items split into its registry groups, in registry order. Each item goes to the first
 * group it matches; items that match none come last. Empty groups are dropped.
 */
export function groupItems(
  section: Section,
  items: readonly Item[],
  featured: Report["featured"],
  minImpact: number,
): ItemGroup[] {
  const buckets = section.groups.map((group) => ({ group, items: [] as Item[] }));
  const rest: Item[] = [];
  for (const item of items) {
    const bucket = buckets.find(({ group }) => matchesGroup(item, group, featured, minImpact));
    (bucket?.items ?? rest).push(item);
  }
  const groups: ItemGroup[] = [...buckets, { group: undefined, items: rest }];
  return groups.filter((bucket) => bucket.items.length > 0);
}

/** Items of a section, in report order. */
export function sectionItems(report: Report, sectionId: string): Item[] {
  return report.items.filter((item) => item.section === sectionId);
}

/** Visuals placed in a deep-dive block. */
export function blockVisuals(item: Item, block: string): Visual[] {
  return item.visuals.filter((visual) => visual.block === block);
}

/** Visuals with no block, or whose block the item's type does not render. */
export function looseVisuals(item: Item, blocks: readonly string[]): Visual[] {
  return item.visuals.filter(
    (visual) => visual.block === undefined || !blocks.includes(visual.block),
  );
}

/** "2026-10-11" -> "2026/10/11/", the report's route below the base path. */
export function reportPath(date: string): string {
  return `${date.replaceAll("-", "/")}/`;
}

/** Leaf visuals of a visual: itself, or the visuals inside a dashboard's tiles. */
export function leafVisuals(visual: Visual): LeafVisual[] {
  if (visual.kind !== "dashboard") return [visual];
  return visual.tiles.flatMap((tile) => (tile.tile === "visual" ? [tile.visual] : []));
}
