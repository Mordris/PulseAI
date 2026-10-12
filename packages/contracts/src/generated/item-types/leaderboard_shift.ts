/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export interface LeaderboardShiftDetail {
  board: string;
  /**
   * @minItems 1
   */
  movers: [RankMove, ...RankMove[]];
  reliability_note: string;
}
export interface RankMove {
  name: string;
  before?: number;
  after: number;
}
