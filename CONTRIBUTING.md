# Contributing

## Setup

    uv sync
    npm install -g pnpm
    pnpm install
    uv run pre-commit install

Node.js stopped bundling Corepack in version 25, so install pnpm with npm. Once pnpm runs inside
this repository it uses the version pinned in `package.json` (`packageManager`).

## Everyday commands

    uv run pytest                                   # Python tests
    pnpm test                                       # TypeScript tests
    uv run ruff format .                            # format Python (before ruff check)
    uv run ruff check . && uv run pyright           # Python lint and types
    pnpm lint && pnpm typecheck                     # TypeScript lint and types
    uv run python scripts/generate_models.py        # after editing schema/*.schema.json
    uv run pulse registry check                     # registries and config agree
    uv run pulse doctor                             # local setup

The report site (see [docs/site.md](docs/site.md)):

    pnpm demo:build                                 # build the demo instance in examples/
    pnpm demo:dev                                   # live reload while editing components
    pnpm demo:check                                 # astro check
    pnpm tokens:check                               # contrast and color gates for every preset
    pnpm demo:e2e                                   # Playwright, axe, screenshots (Docker)
    pnpm --filter @pulseai/site e2e:visual:update   # accept intended visual changes (Linux)
    pnpm --filter @pulseai/contracts generate       # after editing schema/*.schema.json

## Rules

- Contracts live in `schema/`; regenerate models after every schema change and commit them.
- Values live in registries (`taxonomy/`, `sources/`, `locales/`, `defaults/`, `tokens/`), never in
  code. The site's copy comes from locales and its colors, fonts, and sizes from tokens.
- Prefer a maintained open-source project over new code. Add dependencies with `uv add` or
  `pnpm add` so the latest version is resolved and locked; Renovate keeps them current.
- Commits follow Conventional Commits; release-please builds changelogs and versions from them.

## Releasing

Merging the release-please pull request tags `cli-vX.Y.Z`, `contracts-vX.Y.Z`, `tokens-vX.Y.Z`, and
`site-vX.Y.Z` together and publishes the `pulseai` wheel to PyPI through trusted publishing. The npm
packages stay private until M6 builds and publishes them.

One-time repository setup:

1. Create a fine-grained personal access token with read and write access to contents, pull
   requests, and issues, and add it as the `RELEASE_PLEASE_TOKEN` repository secret. The release
   workflow reads that static secret as-is. Pull requests opened with the default `GITHUB_TOKEN`
   never trigger CI, so without this token the release pull request cannot satisfy required
   checks. The workflow falls back to `GITHUB_TOKEN` when the secret is missing. A GitHub App
   would avoid a long-lived personal token, but it needs an `actions/create-github-app-token`
   step in `release-please.yml` to mint its installation token; that is future work.
2. In Settings, Actions, General, enable "Allow GitHub Actions to create and approve pull
   requests".
3. Create the `pypi` environment (Settings, Environments).
4. Configure PyPI trusted publishing for the `pulseai` project with workflow `release-please.yml`
   and environment `pypi`.

## Security checks

Never commit secrets, notification URLs, or tokens; they belong in host secret stores. The
pre-commit `gitleaks` hook blocks most leaks locally; CI repeats gitleaks and TruffleHog (push and
pull request runs scan the commit range; nightly and manual runs scan the full history). If a
secret was ever committed, rotate it first, then remove it from history.

## Commit messages

Use the commit template once per clone: `git config commit.template .gitmessage`.
The pre-commit `commit-msg` hook runs commitlint (Conventional Commits). Pull requests are
squash-merged, so the PR title becomes the commit. CI checks that the title uses a Conventional
Commits type (`feat`, `fix`, and so on); it does not run the full commitlint rule set, so scope
warnings only show up in your local commit-msg hook.
