/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export interface ModelReleaseDetail {
  org: string;
  model: string;
  context_tokens?: number;
  price_in_per_mtok?: number;
  price_out_per_mtok?: number;
  modalities?: string[];
  availability?: string[];
  weights: "open" | "closed" | "partial";
  license?: string;
  try_it?: string;
}
