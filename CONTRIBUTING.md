# Contributing

## Setup

    uv sync
    corepack enable pnpm && pnpm install
    uv run pre-commit install

## Everyday commands

    uv run pytest                                   # Python tests
    pnpm test                                       # TypeScript tests
    uv run ruff check . && uv run pyright           # Python lint and types
    pnpm lint && pnpm typecheck                     # TypeScript lint and types
    uv run python scripts/generate_models.py        # after editing schema/*.schema.json
    uv run pulse registry check                     # registries and config agree
    uv run pulse doctor                             # local setup

## Rules

- Contracts live in `schema/`; regenerate models after every schema change and commit them.
- Values live in registries (`taxonomy/`, `sources/`, `locales/`, `defaults/`), never in code.
- Prefer a maintained open-source project over new code. Add dependencies with `uv add` or
  `pnpm add` so the latest version is resolved and locked; Renovate keeps them current.
- Commits follow Conventional Commits; release-please builds changelogs and versions from them.

## Releasing

Merging the release-please pull request tags `cli-vX.Y.Z` and `contracts-vX.Y.Z` together and
publishes the `pulseai` wheel to PyPI through trusted publishing.

One-time repository setup:

1. Create a GitHub App (preferred) or a fine-grained personal access token with read and write
   access to contents, pull requests, and issues, and make it available to the release job as
   the `RELEASE_PLEASE_TOKEN` repository secret (a token as-is; for a GitHub App, mint its
   installation token in the workflow with `actions/create-github-app-token`). Pull requests
   opened with the default `GITHUB_TOKEN` never trigger CI, so without this token the release
   pull request cannot satisfy required checks. The workflow falls back to `GITHUB_TOKEN` when
   the secret is missing.
2. In Settings, Actions, General, enable "Allow GitHub Actions to create and approve pull
   requests".
3. Create the `pypi` environment (Settings, Environments).
4. Configure PyPI trusted publishing for the `pulseai` project with workflow `release-please.yml`
   and environment `pypi`.
