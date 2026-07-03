---
name: prompt-regression
description: When a PR touches a prompt template or model config, run the affected task_type's eval fixtures on both branches and report score deltas so prompt changes are evidence-based
---

# Prompt Regression

Prompt changes are code changes. A reworded instruction, a shifted few-shot
example, or a model alias swap can quietly regress a tier that was passing.
Run this skill whenever a PR modifies anything under `prompts/`, `config/`
(model aliases, routing), or `schemas/` so the change arrives with a score
delta — not a vibe. This skill delegates all fixture execution to
**eval-harness**; read that skill first to understand tiers, pass-gates, and
fixture layout.

## Workflow

### 1. Detect what changed
```bash
git diff main...HEAD --name-only | grep -E '^(prompts/|config/models|config/routing|schemas/)'
```
If the output is empty, this skill is done. If it hits, note which files.

### 2. Map changed files to affected task_types
```bash
# prompt files are named prompts/<task_type>/<template>.md (or .j2)
# model config keys map to task_type entries in config/models.yaml
git diff main...HEAD --name-only | grep '^prompts/' | cut -d/ -f2 | sort -u
```
For model/routing config changes, open the file and read which `task_type`
entries reference the changed alias — those are all affected.

### 3. Run the eval-harness baseline (main branch)
```bash
git stash   # or use a worktree if you can't stash cleanly
uv run pytest fixtures/<task_type>/ -m "eval" --tb=short -q 2>&1 | tee /tmp/baseline_<task_type>.txt
git stash pop
```
If a baseline score is already recorded in `docs/eval-baselines.md`, use that
instead of re-running — re-running is more trustworthy but costs tokens.

### 4. Run the eval-harness on the branch
```bash
uv run pytest fixtures/<task_type>/ -m "eval" --tb=short -q 2>&1 | tee /tmp/branch_<task_type>.txt
```
Both runs MUST use mocked tools (no live API calls) for tiers 1–2. The
eval-harness skill explains how `tool_mocks` work.

### 5. (Optional) Shadow A/B within a single run
If the harness supports a `--compare-prompt` flag or a `prompt_variant` fixture
field, run old and new prompts side-by-side on the same inputs. This is more
reliable than comparing two separate runs across time.

### 6. Compute and report the delta
For each tier, compute:
```
delta = branch_pass_rate − baseline_pass_rate
```
A negative delta on a gated tier (1 or 2) is a regression. Flag it. An
accepted tradeoff (e.g., tier-1 gains +3 pts, tier-3 loses −5 pts, and tier 3
is ungated) must be logged in `docs/followups.md` before the PR merges — a
silent tradeoff is not an accepted one.

## Guardrails

- A prompt change that regresses a gated tier (pass_gate not met on branch)
  **blocks the PR**. Fix the prompt or lower the expectation and document why.
- Model alias changes that touch a gated task_type follow the same rule.
- If fixtures for the affected task_type don't exist yet, treat that as a P0
  gap: create tier-1 baseline fixtures before merging the prompt change.
  (Reference the eval-harness skill for fixture structure.)
- Never run live-model evals in CI without a cost guard — use mocked tools or
  a spend-capped test account.

## Output

```
## Prompt Regression — <task_type(s)>

Changed files: <list>
Affected task_types: <list>

| Tier | Baseline | Branch | Delta | Gate | Result |
|------|----------|--------|-------|------|--------|
| 1 baseline | 0.92 | 0.88 | −0.04 | 0.90 | REGRESSION |
| 2 nuance   | 0.78 | 0.81 | +0.03 | 0.80 | PASS |
| 3 complexity | 0.61 | 0.65 | +0.04 | none | (diagnostic) |

Regressions: <tier + failing cases + root cause>
Accepted tradeoffs logged: <yes (followups.md entry) / none>

Verdict: PASS / BLOCK — <detail>
```
