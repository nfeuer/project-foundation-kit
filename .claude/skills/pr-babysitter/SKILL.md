---
name: pr-babysitter
description: Watch the open-PR queue on an interval, rebase stale-but-green PRs onto main, surface blockers to a human, and keep CI moving — without auto-merging anything
---

# PR Babysitter

Use this as a recurring loop when a batch of PRs is in flight and the queue needs active tending. It keeps PRs in a mergeable state — rebasing stale ones, kicking CI back into motion, and pinging a human when only a human can unblock. It does **not** merge; it prepares.

Pair with the `/loop` skill for the interval mechanism (e.g. `/loop 10m pr-babysitter`). Hand CI failures to the `ci-watch` skill for the diagnose-fix-push loop. Before rebasing multiple stale PRs at once, run `branch-conflict-check` to find the safer rebase order.

## Workflow

### 1. Fetch the open-PR queue
```bash
gh pr list --state open \
    --json number,headRefName,mergeable,reviewDecision,statusCheckRollup,isDraft,locked,updatedAt
```

### 2. Triage each PR

Classify every open PR with this table, then execute the action column:

| PR state | CI | `mergeable` | `reviewDecision` | Action |
|---|---|---|---|---|
| Up-to-date, all checks pass | Green | `MERGEABLE` | `APPROVED` | Ping human: ready to merge. |
| Stale (behind main) | Green | `MERGEABLE` | any | Rebase onto main, push, hand to `ci-watch`. |
| Stale | Red | any | any | Rebase first, then hand to `ci-watch` for the fix loop. |
| Up-to-date | Red | `MERGEABLE` | any | Hand to `ci-watch`. Do not rebase — that can hide the failure. |
| Up-to-date | Green | `CONFLICTING` | any | Real merge conflict — ping human with the conflicting file list. |
| CI pending / queued | — | any | any | Wait; skip to the next PR and revisit on the next interval. |
| Draft or locked | any | any | any | Skip entirely. Draft = author not ready; locked = another agent is active. |
| `CHANGES_REQUESTED` | any | any | `CHANGES_REQUESTED` | Ping human: review needs a response before CI matters. |

### 3. Rebase a stale PR
```bash
branch=<headRefName>
git fetch origin main
git switch "$branch"
git rebase origin/main
git push --force-with-lease
```
`--force-with-lease` refuses to push if someone else updated the branch since your last fetch. Never use bare `--force`.

### 4. Check for file-set conflicts before rebasing multiple stale PRs
When two or more PRs are stale simultaneously, run **branch-conflict-check** (or `check.sh`) on each to find the safer rebase order. Rebase the depended-on PR first; let its CI green before rebasing anything that overlaps it.

### 5. After a rebase push, hand off to ci-watch
Don't wait in-line — dispatch the **ci-watch** skill for the rebased branch and move on to the next PR. Collect results when the interval fires again.

### 6. Batch human pings into one message
Collect every PR that needs human action across the full queue, then send a single consolidated message: PR number, specific blocker, suggested next step. One ping per loop run, not one per PR.

## Guardrails

- **Never auto-merge.** Merging is a deliberate human act. Prepare and present; don't decide.
- **Never force-push someone else's active branch.** If the branch received a non-bot commit in the last 10 minutes, skip it and note it as "possibly active."
- **Never rebase a red PR to mask failures.** Diagnose and fix first (`ci-watch`), then rebase if the branch is still stale afterward.
- **Never touch locked or draft PRs.** Locked = in-flight by another agent; draft = author not ready.
- **Never merge a red or `CONFLICTING` PR.** Both are human-decision blockers.
- **Stop thrashing.** If the same PR has been rebased twice in one loop iteration and CI is still red, escalate to the human rather than rebasing a third time.

## Output

Emit this summary at the end of each loop iteration:

```
## PR Queue  <ISO-timestamp>

| PR | Branch | CI | Action taken | Human needed |
|---|---|---|---|---|
| #<n> | <ref> | green | rebased + pushed → ci-watch | — |
| #<m> | <ref> | green | none | merge-ready (green + approved) |
| #<k> | <ref> | red | ci-watch dispatched | — |
| #<j> | <ref> | green | — | real conflict in <files> |

Human queue:
- #<m>: ready to merge (green + approved)
- #<j>: merge conflict — <files> — resolve manually

Next check in: <interval>
```
