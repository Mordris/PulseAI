# Scorecard findings

Assessment date: 2026-10-29. Baseline: `0b60c83` on `main`.

The [Scorecard workflow](../.github/workflows/scorecard.yml) continues to run all checks and upload
its results to GitHub code scanning. Closing an alert as an accepted risk does not improve the
Scorecard score or establish that the corresponding practice is in place.

| Alert | Evidence and disposition |
|---|---|
| [Security-Policy #2](https://github.com/Mordris/PulseAI/security/code-scanning/2) | Fixed by linking directly to the enabled private vulnerability reporting form in `SECURITY.md`. The policy already specifies supported versions and a 7-day acknowledgement target. |
| [Fuzzing #3](https://github.com/Mordris/PulseAI/security/code-scanning/3) | Fixed by adding fast-check property tests to the contracts package's existing Vitest suite, which runs in Node CI. Generated JSON exercises every schema validator for crash and mutation safety; generated report fields and non-web source URLs test rejection at the input boundary. |
| [Branch-Protection #1](https://github.com/Mordris/PulseAI/security/code-scanning/1) | Accepted risk for a solo-maintained project: the owner must be able to merge their own PRs after CI passes. The active `main` ruleset requires pull requests, all configured status checks, resolved review threads, and linear history, and blocks deletion and force pushes, with no bypass actors. It requires zero approving reviews and does not require a code owner or last-push approval. Revisit when another maintainer can review. |
| [Code-Review #5](https://github.com/Mordris/PulseAI/security/code-scanning/5) | Accepted risk: Scorecard found 0/9 approved changesets. The project has one collaborator, and GitHub does not allow authors to approve their own PRs. At the owner's request, required reviews remain disabled so the owner can merge after CI passes. Existing automated checks and agent reviews do not establish independent GitHub approvals. Revisit when independent review is available; historical approvals must not be fabricated. |
| [Maintained #4](https://github.com/Mordris/PulseAI/security/code-scanning/4) | Accepted temporary limitation: GitHub records repository creation on 2026-10-11, and Scorecard assigns zero to projects younger than 90 days. Recent merged work demonstrates activity but cannot establish a 90-day history. Revisit on or after 2027-01-09; age alone does not guarantee a passing score. |
| [CII-Best-Practices #6](https://github.com/Mordris/PulseAI/security/code-scanning/6) | Accepted risk: no OpenSSF Best Practices badge enrollment or award is currently evidenced. The maintainer can enroll at [bestpractices.dev](https://www.bestpractices.dev/) and assess the [criteria](https://www.bestpractices.dev/en/criteria). This project does not claim a badge or attest to unmet criteria. Revisit on enrollment and after the assessment. |

The four accepted findings remain useful process limitations. Their GitHub dismissal reason is
`won't fix`, with a comment recording the present constraint and the condition for reassessment.
The two implemented fixes should be closed by a successful Scorecard scan of the merged changes.
