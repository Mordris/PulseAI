/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export interface SecurityAdvisoryDetail {
  advisory_id: string;
  cvss?: number;
  severity: "low" | "medium" | "high" | "critical";
  affected: string;
  fixed_in?: string;
  exploited_in_wild: boolean;
  fix_command?: string;
}
