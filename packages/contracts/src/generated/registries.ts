/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

export type Id = string;
export type Path = string;

/**
 * Which registries exist, where their files live, and which schema validates them.
 */
export interface RegistriesCatalog {
  schema_version: 1;
  /**
   * Variables allowed in source URL and query templates, e.g. {date}.
   */
  template_variables: string[];
  /**
   * @minItems 1
   */
  registries: [RegistrySpec, ...RegistrySpec[]];
}
export interface RegistrySpec {
  id: Id;
  schema: string;
  /**
   * Engine files, relative to the engine root. Globs and {variables} allowed.
   *
   * @minItems 1
   */
  paths: [Path, ...Path[]];
  /**
   * Instance override files; defaults to paths.
   *
   * @minItems 1
   */
  instance_paths?: [Path, ...Path[]];
  /**
   * Key holding the id-keyed list when several engine files are combined.
   */
  list_key?: string;
  /**
   * False makes the registry engine-only: instance files are never read, so an instance cannot change what the engine runs.
   */
  instance_overridable?: boolean;
}
