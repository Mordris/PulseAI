import { describe, expect, it } from "vitest";
import { ALL, type ItemFacets, matchesFilters, NO_FILTERS } from "../src/lib/filters.ts";

describe("filters", () => {
  const item: ItemFacets = {
    section: "models",
    type: "paper",
    impact: 3,
    confidence: "confirmed",
    update: false,
  };

  it("passes everything without filters", () => {
    expect(matchesFilters(item, NO_FILTERS)).toBe(true);
  });

  it("applies each filter", () => {
    expect(matchesFilters(item, { ...NO_FILTERS, section: "oss" })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, type: "paper" })).toBe(true);
    expect(matchesFilters(item, { ...NO_FILTERS, minImpact: 4 })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, confidence: "reported" })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, status: "updates" })).toBe(false);
    expect(matchesFilters({ ...item, update: true }, { ...NO_FILTERS, status: "new" })).toBe(false);
    expect(matchesFilters(item, { ...NO_FILTERS, section: ALL, status: ALL })).toBe(true);
  });
});
