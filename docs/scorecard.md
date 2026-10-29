# Scorecard findings

Assessment date: 2026-10-29. Baseline: `0b60c83` on `main`.

The [Scorecard workflow](../.github/workflows/scorecard.yml) continues to run all checks and upload
its results to GitHub code scanning. Closing an alert as an accepted risk does not improve the
Scorecard score or establish that the corresponding practice is in place.

| Alert | Evidence and disposition |
|---|---|
| [Security-Policy #2](https://github.com/Mordris/PulseAI/security/code-scanning/2) | Fixed by linking directly to the enabled private vulnerability reporting form in `SECURITY.md`. The policy already specifies supported versions and a 7-day acknowledgement target. |
| [Fuzzing #3](https://github.com/Mordris/PulseAI/security/code-scanning/3) | Fixed by adding fast-check property tests to the contracts package's existing Vitest suite, which runs in Node CI. Generated JSON exercises every schema validator for crash and mutation safety; generated report fields and non-web source URLs test rejection at the input boundary. |
| [Branch-Protection #1](https://github.com/Mordris/PulseAI/security/code-scanning/1) | Strengthened at the owner's request: require one independent approving review, dismiss stale approvals, and require approval of the latest push by someone other than its pusher. Preserve required status checks, resolved review threads, linear history, and deletion/force-push blocks, with no bypass actors. A second reviewer and code-owner approval are not required; Scorecard may still score those additional controls separately. |
| [Code-Review #5](https://github.com/Mordris/PulseAI/security/code-scanning/5) | Accepted historical limitation: Scorecard found 0/9 approved changesets. The updated policy requires independent approval for future merges, including this remediation PR. It cannot add approvals to past changesets. Revisit after genuinely approved PRs populate the scoring window; historical approvals must not be fabricated. |
| [Maintained #4](https://github.com/Mordris/PulseAI/security/code-scanning/4) | Accepted temporary limitation: GitHub records repository creation on 2026-10-11, and Scorecard assigns zero to projects younger than 90 days. Recent merged work demonstrates activity but cannot establish a 90-day history. Revisit on or after 2027-01-09; age alone does not guarantee a passing score. |
| [CII-Best-Practices #6](https://github.com/Mordris/PulseAI/security/code-scanning/6) | Accepted risk: no OpenSSF Best Practices badge enrollment or award is currently evidenced. The maintainer can enroll at [bestpractices.dev](https://www.bestpractices.dev/) and assess the [criteria](https://www.bestpractices.dev/en/criteria). This project does not claim a badge or attest to unmet criteria. Revisit on enrollment and after the assessment. |

The three accepted findings remain useful process limitations. Their GitHub dismissal reason is
`won't fix`, with a comment recording the present constraint and the condition for reassessment.
The two implemented fixes should be closed by a successful Scorecard scan of the merged changes.
Branch protection is assessed again after the live ruleset is updated. Only the owner is currently
a repository collaborator; an independent reviewer with write access must be available to unblock
merges. The review requirement must not be bypassed to merge this remediation.
