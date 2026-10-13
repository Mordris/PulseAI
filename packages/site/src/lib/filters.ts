/** Filter values; ALL means "no restriction" for a select. */
export const ALL = "all";
export const STATUS_NEW = "new";
export const STATUS_UPDATES = "updates";

/** What the filter row can see of one item (from its data-* attributes). */
export interface ItemFacets {
  section: string;
  type: string;
  impact: number;
  confidence: string;
  update: boolean;
}

export interface Filters {
  section: string;
  type: string;
  minImpact: number;
  confidence: string;
  status: string;
}

export const NO_FILTERS: Filters = {
  section: ALL,
  type: ALL,
  minImpact: 1,
  confidence: ALL,
  status: ALL,
};

/** Whether any filter differs from its default. */
export function isFiltering(filters: Filters): boolean {
  return (Object.keys(NO_FILTERS) as (keyof Filters)[]).some(
    (key) => filters[key] !== NO_FILTERS[key],
  );
}

export function matchesFilters(facets: ItemFacets, filters: Filters): boolean {
  if (filters.section !== ALL && facets.section !== filters.section) return false;
  if (filters.type !== ALL && facets.type !== filters.type) return false;
  if (facets.impact < filters.minImpact) return false;
  if (filters.confidence !== ALL && facets.confidence !== filters.confidence) return false;
  if (filters.status === STATUS_NEW && facets.update) return false;
  if (filters.status === STATUS_UPDATES && !facets.update) return false;
  return true;
}
