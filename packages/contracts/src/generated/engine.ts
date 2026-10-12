/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Id = string;

/**
 * Engine requirements checked by pulse doctor.
 */
export interface EngineRegistry {
  schema_version: 1;
  /**
   * How long pulse doctor waits for each tool's version command.
   */
  tool_timeout_seconds: number;
  /**
   * @minItems 1
   */
  tools: [Tool, ...Tool[]];
}
export interface Tool {
  id: Id;
  /**
   * Prints the version. The token {python} means the running interpreter.
   *
   * @minItems 1
   */
  command: [string, ...string[]];
  /**
   * First capture group is the version.
   */
  version_regex: string;
  /**
   * PEP 440 specifier, e.g. >=3.12.
   */
  specifier: string;
  required: boolean;
  hint: string;
}
