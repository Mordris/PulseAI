# Security policy

Report vulnerabilities privately through
[GitHub's private vulnerability reporting form](https://github.com/Mordris/PulseAI/security/advisories/new).
Please do not open public issues for security problems. Expect an acknowledgement within 7 days.

Supported versions: the latest release.

## Trust model

An instance (your `pulse-instance` repository) is data, not code: its YAML and JSON files are
validated against the engine's schemas and never executed. The one registry that names commands,
the tool requirements in `defaults/engine.yaml` that `pulse doctor` runs, is engine-only. The
loader never reads an instance's copy of it (`instance_overridable: false` in
`defaults/registries.yaml`), so a pull request or a stale clone of an instance cannot make
`pulse doctor` run something else.

## Automated controls

| Control | Where |
|---|---|
| Secret leaks (pattern + verified) | `secret-scan.yml`: gitleaks with `.gitleaks.toml`, TruffleHog; push and PR runs scan the pushed or PR commit range, nightly and manual runs scan the full history |
| Secrets before they reach git | pre-commit `gitleaks` hook |
| Vulnerable dependencies | `vulnerability-scan.yml`: OSV-Scanner over `uv.lock` and `pnpm-lock.yaml` on PRs and nightly; `dependency-review.yml` blocks new vulnerable or disallowed-license dependencies |
| Code scanning | `codeql.yml` (Python, TypeScript, Actions) |
| Generated adversarial inputs | `packages/contracts/test/fuzz.test.ts`: fast-check exercises schema validators, unexpected report fields, and source URL schemes on every Node CI run |
| Workflow security | `workflow-security.yml` (zizmor); SHA-pinned actions; `permissions: {}` defaults; `persist-credentials: false` |
| Runtime egress audit | `step-security/harden-runner` as the first step of every job |
| Supply chain | `scorecard.yml` (OpenSSF Scorecard), Renovate updates, release SBOM (SPDX) and build provenance attestations |

## Repository settings

Repository settings (features, merge rules, security features, topics, and the `main` ruleset with
required checks) live in `.github/repository.yml` and are applied with
`uv run python scripts/github/apply_repo_settings.py --repo OWNER/NAME` (use `--dry-run` first).
Also allow only SHA-pinned actions and set the default `GITHUB_TOKEN` permission to read-only under
Settings → Actions → General, and keep CodeQL default setup off (the workflow is the source of
truth).

Checks that come from reusable workflows report as `<job> / <inner job>`; the OSV-Scanner pull
request check is `scan-pr / osv-scan`. When you add or rename a job, confirm the reported name in a
CI run before adding it to `ruleset.required_checks` in `.github/repository.yml`.

See [Scorecard findings](docs/scorecard.md) for the evidence and limitations behind the project's
Scorecard alert dispositions.
