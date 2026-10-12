/* Generated from schema/ by packages/contracts/scripts/generate-types.ts. Do not edit. */

/**
 * Agent roles (taxonomy/roles.yaml); config.models_by_role assigns a model to each.
 */
export interface RolesRegistry {
  schema_version: 1;
  /**
   * @minItems 1
   */
  roles: [Role, ...Role[]];
}
export interface Role {
  id: string;
  description: string;
}
