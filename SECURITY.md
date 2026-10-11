# Security policy

Report vulnerabilities privately through GitHub security advisories
("Report a vulnerability" on the repository's Security tab). Please do not open public issues for
security problems. Expect an acknowledgement within 7 days.

Supported versions: the latest release.

## Automated controls

| Control | Where |
|---|---|
| Secret leaks (pattern + verified) | `secret-scan.yml`: gitleaks with `.gitleaks.toml`, TruffleHog; push and PR runs scan the pushed or PR commit range, nightly and manual runs scan the full history |
| Secrets before they reach git | pre-commit `gitleaks` hook |
| Vulnerable dependencies | `vulnerability-scan.yml`: OSV-Scanner over `uv.lock` and `pnpm-lock.yaml` on PRs and nightly; `dependency-review.yml` blocks new vulnerable or disallowed-license dependencies |
| Code scanning | `codeql.yml` (Python, TypeScript, Actions) |
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

Checks that come from reusable workflows (the OSV-Scanner jobs in `vulnerability-scan.yml`) report
as `<job> / <inner job>`. Confirm their exact names from the first CI run, then add them to
`ruleset.required_checks` in `.github/repository.yml`.
