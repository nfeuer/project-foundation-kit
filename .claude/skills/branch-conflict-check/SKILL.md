---
name: branch-conflict-check
description: Detect file-level overlap between the current branch and every other open PR so merge order gets decided deliberately, not discovered at conflict time
---

# Branch Conflict Check

Run this when you open a PR or any time you want to verify merge safety. It answers: _"which other open PRs touch the same files I do?"_ The `parallel-work` skill prevents live worktree collisions; this is the complement — it prevents the merge-time collisions that slip through when two PRs land on the same path days apart.

## Workflow

### 1. Get this branch's changed files
```bash
git diff main...HEAD --name-only
```
Replace `main` with your base branch if it differs (`master`, `develop`, etc.).

### 2. List other open PRs
```bash
gh pr list --state open --json number,headRefName,url
```

### 3. Fetch changed files per PR
```bash
gh pr view <n> --json files --jq '.files[].path'
```

Or run the bundled helper, which does all three steps and prints overlaps grouped by PR:
```bash
bash .claude/skills/branch-conflict-check/check.sh [base-branch]
```

### 4. Compute the intersection

Compare the file sets manually or let `check.sh` do it with `comm -12`. Any path in both sets is a potential merge conflict.

### 5. Act on overlaps

| Situation | Action |
|---|---|
| No overlap | Merge in any order. |
| Overlap, different layers (e.g. schema + UI calling it) | Sequence: schema PR first, then the caller. |
| Overlap in the same function or same test file | Rebase the later branch onto the earlier one, or split the change at the source. |
| Overlap is intentional (shared fixture refactor) | Note it in both PR bodies; merge the depended-on PR first and document the order. |

When uncertain: merge the smaller or less-dependent PR first, then rebase the other onto the updated base.

## Guardrails

- This check is advisory — it does not block merges. An overlap means "coordinate," not "abandon."
- If `gh` is unavailable or not authenticated, `check.sh` exits 0 silently. Verify manually via the GitHub PR file-diff UI in that case.
- Re-run after any rebase or force-with-lease push to a base branch — the changed-file set can shift.

## Output

```
## Branch Conflict Check
- Branch: <current-branch>
- Base: <main/master>
- Changed files on this branch: <N>
- Other open PRs checked: <K>

Overlaps:
  PR #<n>  (<head-ref>): <file1>, <file2>
  PR #<m>  (<head-ref>): <file3>

  — OR —

  None found.

Action: <merge in any order / rebase <branch> onto <branch> first / split <what> / coordinate merge order: #<n> then #<m>>
```
