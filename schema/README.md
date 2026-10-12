# Schemas

JSON Schema (draft 2020-12) files here are the single source of truth for every PulseAI contract.
Python models are generated from the top-level `*.schema.json` files (`scripts/generate_models.py`);
TypeScript builds Zod validators from the same files (`packages/contracts`).

Rules:
- `$id` is `urn:pulseai:schema:<name>`; objects use `additionalProperties: false`.
- Give every object that should become a named model a unique `title`.
- Do not use `if`/`then`/`else`; use `oneOf` with `const` discriminators (Zod requirement).
- `item-types/*.schema.json` validate an item's `detail` object; the type registry
  (`taxonomy/item-types.yaml`) names the schema file for each type.
