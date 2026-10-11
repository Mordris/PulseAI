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

## One-time repository settings (owner)

1. Settings → Code security: enable secret scanning **and push protection**, private vulnerability
   reporting, Dependabot alerts (updates stay with Renovate), and CodeQL default setup off (the
   workflow is the source of truth).
2. Settings → Rules: protect `main` — require pull requests, linear history, and these checks:
   `python (3.12)`, `python (3.15)`, `node`, `analyze`, `review`, `gitleaks`, `trufflehog`,
   `scan-pr`, `zizmor`. Checks that come from reusable workflows (for example OSV `scan-pr`)
   report as `<job> / <inner job>`; confirm their exact names from the first CI run before adding
   them to the ruleset.
3. Settings → Actions → General: allow only SHA-pinned actions and set the default
   `GITHUB_TOKEN` permission to read-only.
