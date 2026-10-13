/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export interface ReleaseDetail {
  product: string;
  version: string;
  previous_version?: string;
  /**
   * @minItems 1
   */
  changelog: [ChangelogEntry, ...ChangelogEntry[]];
  verdict: "adopt" | "trial" | "assess" | "hold";
  snippet?: string;
  migration_notes?: string;
}
export interface ChangelogEntry {
  tag: "new" | "fix" | "breaking" | "perf" | "deprecation" | "security";
  text: string;
}
