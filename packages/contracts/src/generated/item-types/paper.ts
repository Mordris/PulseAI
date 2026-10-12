/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export interface PaperDetail {
  arxiv_id?: string;
  venue?: string;
  peer_reviewed: boolean;
  /**
   * @minItems 1
   */
  authors: [string, ...string[]];
  affiliations?: string[];
  tldr: string;
  plain_explanation: string;
  problem: string;
  key_idea: string;
  /**
   * @minItems 1
   * @maxItems 8
   */
  method_steps:
    | [string]
    | [string, string]
    | [string, string, string]
    | [string, string, string, string]
    | [string, string, string, string, string]
    | [string, string, string, string, string, string]
    | [string, string, string, string, string, string, string]
    | [string, string, string, string, string, string, string, string];
  /**
   * @minItems 1
   */
  critical_review: [string, ...string[]];
  reproducibility: Reproducibility;
  takeaway: string;
  reading_guide: ReadingGuide;
}
export interface Reproducibility {
  code_url?: string;
  data_url?: string;
  weights_url?: string;
  license?: string;
}
export interface ReadingGuide {
  sections: string[];
  glossary: {
    [k: string]: string | undefined;
  };
  reading_minutes: number;
  difficulty: "intro" | "intermediate" | "advanced";
}
