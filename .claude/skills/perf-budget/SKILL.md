---
name: perf-budget
description: Catch hot-path and external/model-call latency regressions before they reach production — compare p95 per operation against configured budgets and a stored baseline, fail the PR on regression, and offer to ratchet the baseline down on improvement
---

# Performance Budget

The performance analogue of the cost guardrail. Where the cost gate prevents
overspending money, this gate prevents overspending time — catching regressions
in hot paths and external/model calls during review, before they affect users.
It enforces two thresholds per operation: an **absolute budget** (the p95 must
not exceed N ms) and a **baseline tolerance** (the p95 must not regress beyond a
stored per-path baseline by more than `tolerance_pct`). When a path improves,
it offers to ratchet the baseline down — one-way, like the coverage ratchet.

**Profile-driven.** Commands and thresholds below read from `.claude/kit.yaml`.
Steps tagged `# kit.yaml → <key>` use the value at that key if set; an empty
string or absent key means skip the step and mark it N/A. This skill is invoked
from **pre-pr** as a capability-gated step.

## Workflow

### 1. Check the capability gate

Open `.claude/kit.yaml` and read `capabilities.perf.enabled`. If it is `false`
or absent, skip all remaining steps and report **N/A**. This skill ships
disabled by default — it is most valuable on a deployed service with real
traffic and an `invocation_log` table or a reproducible benchmark suite. Enable
it once those preconditions exist rather than running it against a library or a
project whose latency data does not yet exist.

### 2. Read budgets and baseline

Read the per-path budget map from `capabilities.perf.budgets`. It is a flat
YAML map of `operation_name: p95_ms`, for example:

```yaml
# kit.yaml → capabilities.perf.budgets
capabilities:
  perf:
    budgets:
      llm.chat_completion: 2000
      db.task_list: 50
      db.task_write: 30
```

Read the baseline file path from `capabilities.perf.baseline_file` (default:
`.perf-baseline.json`). The file is a JSON object mapping operation name to the
last accepted p95 ms, for example:

```json
{ "llm.chat_completion": 1900, "db.task_list": 44, "db.task_write": 27 }
```

If the baseline file does not exist, treat every path's baseline as the budget
value — the first run will create it.

Read the regression tolerance from `capabilities.perf.tolerance_pct` (default:
`10`). A path that regresses by **more** than this percentage above its stored
baseline triggers a failure even if it is still under its absolute budget.

### 3. Gather latencies

The source of latency data depends on `capabilities.perf.source`:

**`"benchmark"`** — run the configured benchmark command and parse its output:

```bash
# kit.yaml → capabilities.perf.benchmark_cmd
uv run pytest tests/benchmarks/ --benchmark-json=.benchmark-results.json -q
```

Parse `.benchmark-results.json`. For each benchmark, extract the `name`,
`stats.median` (p50, in seconds), and `stats.ops` or use `stats.q95` / build
a p95 from the sorted sample if available. Convert to milliseconds.
Map benchmark names to the operation keys in `capabilities.perf.budgets` — the
benchmark `name` field must match a budget key exactly, or be prefixed with
`bench_` that strips cleanly (e.g. `bench_db.task_list` → `db.task_list`).
Skip benchmarks that have no matching budget key.

**`"log"`** — query the spend/telemetry table for recent latency observations:

```sql
-- kit.yaml → capabilities.llm.spend_table (default: invocation_log)
SELECT
    operation,
    latency_ms
FROM invocation_log
WHERE timestamp >= datetime('now', '-7 days')
  AND latency_ms IS NOT NULL
ORDER BY operation, latency_ms;
```

Group rows by `operation`. Compute p50 and p95 from the sorted sample using
nearest-rank: p50 = row at index `ceil(0.50 * n)`, p95 = row at index
`ceil(0.95 * n)`. Require at least 20 observations per path to consider the
estimate reliable; paths with fewer observations are shown in the output but
marked `(sparse — N obs)` and do not block the gate.

### 4. Compare against budgets and baseline

For each budgeted path, apply both checks:

| Check | Condition | Result |
|---|---|---|
| Absolute budget | p95 > budget_ms | **FAIL** |
| Baseline regression | p95 > baseline_ms × (1 + tolerance_pct / 100) | **FAIL** |
| Baseline improvement | p95 < baseline_ms | PASS — offer to ratchet |
| Within tolerance | otherwise | PASS |

A path **fails** if either check is violated. Paths not present in
`capabilities.perf.budgets` are ignored.

### 5. Ratchet the baseline down on improvement

When one or more paths are strictly faster than their baseline, offer to lower
the baseline to the current p95. This is a one-way gate: baselines only
decrease (tighter) — never increase automatically. Ratcheting locks in the
improvement so future regressions back to the old number are caught.

To accept the ratchet for an improved path, write the updated JSON to the
baseline file and stage it:

```bash
# update .perf-baseline.json with the new per-path p95 values, then:
git add .perf-baseline.json
```

Confirm with the author before committing — it is a deliberate policy tightening,
not a mechanical fix. A baseline change commit message should read:
`perf: ratchet baseline — <path> <old>→<new> ms`.

### 6. Fail the gate on regression

If any path failed either check, the gate **FAILS**. The author must either:

- Investigate and fix the regression (preferred), or
- Explicitly acknowledge that the workload changed and the new baseline is
  correct — in which case update the baseline file with a commit message
  explaining why and update `capabilities.perf.budgets` if the absolute budget
  also needs to move.

Do not silently raise the baseline. Do not comment out a budgeted path without
a note explaining the removal.

## Notes

- This skill is invoked from **pre-pr** as step 17 (capability-gated). Add it
  to the pre-pr checklist output as: `- [ ] Perf budget: <results / N/A>`.
- This skill is most valuable on a **service with real traffic** (source: "log")
  or a project with a **stable benchmark suite** (source: "benchmark"). On a
  library without either, enable it only after both preconditions exist.
  It ships disabled by default (`capabilities.perf.enabled: false`).
- The runtime companion to this gate is `templates/perf_budget.py` — a
  `PerfBudget` context manager / decorator that emits `perf_budget_exceeded`
  warnings into the same observability pipeline as fallback alerts. Wire it
  around hot paths so the `invocation_log` table accumulates the latency data
  this gate reads.
- p95 is the right aggregation for a latency gate: it filters single-sample
  noise while surfacing tail behavior that affects real users. Do not gate on
  mean — means hide the tail.

## Output

```
## Performance Budget

Source: <benchmark | log — last 7 days>

| Path | p50 ms | p95 ms | Budget ms | Baseline ms | Δ baseline | Verdict |
|---|---|---|---|---|---|---|
| llm.chat_completion | 1 120 | 1 840 | 2 000 | 1 900 | -60 ms (-3.2 %) | PASS |
| db.task_list | 42 | 91 | 50 | 80 | +11 ms (+13.8 %) | FAIL — budget exceeded |
| db.task_write | 18 | 29 | 30 | 31 | -2 ms (-6.5 %) | PASS — improved |

Overall verdict: FAIL — 1 path exceeded budget

Ratchet action: <none | offered to lower baseline — db.task_write 31 ms → 29 ms>
```
