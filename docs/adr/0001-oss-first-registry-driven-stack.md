# ADR 0001: OSS-first, registry-driven stack

- Status: accepted
- Date: 2026-10-11

## Context

PulseAI must be scalable, generic, and easy for others to run and extend. Hand-written renderers,
fetchers, and hardcoded taxonomies would be costly to maintain and hard to customize.

## Decision

- Use maintained open-source projects for every concern that has one; custom code is thin glue.
- JSON Schema files are the single source of truth; Python models are generated and TypeScript
  builds Zod validators from the same files.
- Sections, item types, sources, roles, locales, defaults, and tool requirements are registries
  validated against those schemas. Instances override them by id without code changes.
- Dependencies start at their latest stable versions, are locked, and are kept current by Renovate.

## Consequences

- New sections, types, sources, and languages are data changes.
- Schema constructs must work in both jsonschema (Python) and Zod (no if/then/else).
- CI must check generated models for drift and validate all registries in both languages.
