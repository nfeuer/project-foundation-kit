---
name: coverage-ratchet
description: Prevent test coverage from silently eroding — compare the current run against a stored baseline, fail if it dropped, and offer to lock in a higher baseline when it rose
---

# Coverage Ratchet

Coverage numbers that can only go up (or stay flat) are a one-way gate. This
skill reads the project's baseline from `.claude/kit.yaml` and the stored
baseline file, runs the test suite with coverage, and enforces the floor. It
does not reason about *which* paths are covered — use the **test-gap-analyzer**
agent for that. This enforces the *number*.

## Workflow

### 1. Read the baseline path
Open `.claude/kit.yaml` and read `capabilities.coverage.baseline_file` (default:
`.coverage-baseline`). That file contains a single float, e.g. `82.4`.

If the file does not exist, treat baseline as `0.0` and proceed — the first run
will create it.

### 2. Run the test suite with coverage
```bash
# Python / uv — adjust to your toolchain (kit.yaml → toolchain.test)
uv run pytest tests/unit/ -m "not slow and not llm" \
  --cov=src --cov-report=term-missing --cov-report=json -q
```
Parse the total line coverage percentage from `coverage.json` → `.totals.percent_covered`
(or from the terminal summary line `TOTAL ... XX%`).

### 3. Compare and decide

| Outcome | Action |
|---|---|
| Current < baseline | **FAIL** — report the delta; do not update the baseline. List files with the largest drops to guide the author. |
| Current == baseline | PASS — no action needed. |
| Current > baseline | PASS — offer to ratchet the baseline UP to the new value. Never lower it automatically. |

**Strictness** (`gates.strictness` in `kit.yaml`, see `docs/PROFILE.md`):
at `prototype`, a drop is reported as `ADVISORY` instead of FAIL and does not
block the PR — the numbers are informational until there is a baseline worth
defending. At `production`, `ratchet_enabled: true` with a missing baseline
file is a FAIL rather than a first-run bootstrap — generate the baseline before
gating.

To ratchet up: write the new percentage (two decimal places) to the baseline
file and stage it:
```bash
echo "87.30" > .coverage-baseline
git add .coverage-baseline
```
Confirm with the author before committing a baseline change — it's a deliberate
policy update, not a mechanical fix.

### 4. Coverage drops are always intentional or a bug
If coverage dropped, the author must either:
- Add tests to restore it (preferred), or
- Explicitly acknowledge that the deleted/changed code was over-counted and the
  real-world coverage is unchanged — in which case update the baseline with a
  commit message explaining why.

Do not silently lower the baseline. Do not bypass with `# pragma: no cover`
without a comment explaining why.

## Notes

- This skill complements **test-gap-analyzer**, which reasons about *meaningful*
  gaps (untested branches, missing edge cases). Run that agent after this one
  passes to catch coverage that is numerically present but logically shallow.
- Baseline file path is read from `.claude/kit.yaml` every run, so changing the
  project's coverage configuration requires updating `kit.yaml`, not this skill.

## Output

```
## Coverage Ratchet

- Current:   <XX.XX %>
- Baseline:  <XX.XX %> (from <.coverage-baseline>)
- Delta:     <+N.NN % | -N.NN % | 0.00 %>
- Verdict:   PASS | FAIL — coverage dropped N.NN % below baseline

Ratchet action: <none | offered to raise baseline to XX.XX %>
```
