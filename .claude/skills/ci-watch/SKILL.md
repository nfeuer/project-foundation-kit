---
name: ci-watch
description: After opening or pushing a PR, watch its CI run to completion and fix any failure — lint, types, tests, build — then re-push until green, instead of leaving a red PR
cost: cheap
protects: "A pull request's CI run gets watched until it finishes, and any failure gets diagnosed and fixed automatically instead of being left red."
requires: "GitHub CLI (gh) authenticated"
gate_key: none
ci_job: none
---

# CI Watch-and-Fix

A PR isn't done when it's opened — it's done when CI is green. Use this skill
immediately after `gh pr create` or any push to a PR branch. It watches the run,
and if anything fails, diagnoses and fixes it in the same worktree, then
re-pushes and watches again. The `pre-pr` skill should catch most of this
locally; this is the backstop for the environment-specific failures that only
surface in CI (missing lockfile entry, OS-specific test, cache mismatch).

**Profile-driven.** Toolchain commands referenced below (lint, types, tests, install) come
from `.claude/kit.yaml`; the literals shown are the defaults for a Python/uv project.

Work in the PR's worktree the whole time. Never fix CI by editing the `trunk_branch`
(read from `.claude/kit.yaml`, default: `main`).

## Workflow

### 1. Find the run and watch it
```bash
branch=$(git branch --show-current)
gh run watch "$(gh run list --branch "$branch" --limit 1 --json databaseId -q '.[0].databaseId')" --exit-status
```
`--exit-status` makes the command exit non-zero if the run fails, so you can
branch on it. If `gh run watch` returns success, you're green — report and stop.

> `gh run watch` polls until completion, so it can block a while. If you'd rather
> not hold the turn, use the `/loop` skill or `ScheduleWakeup` to re-check on an
> interval matched to your CI's typical duration.

### 2. On failure, get the logs for the failed jobs only
```bash
run_id=$(gh run list --branch "$branch" --limit 1 --json databaseId -q '.[0].databaseId')
gh run view "$run_id" --log-failed
```

### 3. Diagnose before you touch anything
Use the **systematic-debugging** skill. Read the actual error — don't
pattern-match to a fix. Map the failure to its cause:

> Reproduce-locally commands below are the defaults; substitute the value from the
> matching key in `.claude/kit.yaml` if your project overrides it:
> `toolchain.lint` / `toolchain.typecheck` / `toolchain.test` / `toolchain.install`.

| CI job failed | Reproduce locally (`kit.yaml` key) | Typical fix |
|---|---|---|
| lint (ruff) | `ruff check src/ tests/` (`toolchain.lint`) | `ruff check --fix`, then hand-fix the rest |
| types (mypy) | `mypy src/` (`toolchain.typecheck`) | add/repair annotations; don't `# type: ignore` to silence |
| tests | `pytest <the failing node id>` (`toolchain.test`) | fix the code or the test — establish which is wrong first |
| build | run the build command (`toolchain.build`) | missing dep in lockfile, bad import path |
| lockfile drift | `uv lock` / `npm install` (`toolchain.install`) | commit the regenerated lockfile |

Reproduce the failure locally first. A fix you can't reproduce failing is a fix
you can't verify.

### 4. Fix, re-run the local gate, push
Apply the fix, then re-run the relevant `pre-pr` steps locally to confirm.
Commit with a message that says what CI caught:
```bash
git commit -am "fix(ci): <what failed> — <what you changed>"
git push
```

### 5. Watch again
Return to step 1. Repeat until green. If the **same** job fails a third time on
the same cause, stop and report — you're likely misreading the failure, and
thrashing wastes CI minutes. Escalate with the logs rather than guessing again.

## Guardrails
- **Never make CI pass by weakening the check** (deleting the assertion, adding a
  blanket ignore, marking the test skip) unless the check itself is genuinely
  wrong — and if it is, say so explicitly in the commit and PR body.
- **Don't disable a CI job** to get green. Fix the cause.
- **A flaky test is a finding, not a nuisance.** If a test passes on re-run with
  no code change, log it in the follow-ups file (`docs/followups.md` by default)
  rather than silently moving on.

## Output
```
## CI Watch
- PR: #<n>
- Runs observed: <k>
- Failures fixed: <lint / types / tests / build / none>
- Final status: GREEN / STILL RED — <blocking failure + logs>
```
