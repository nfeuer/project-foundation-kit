---
name: cost-check
description: Query the invocation/spend log for current API spend vs daily and monthly budget thresholds and report a projected month-end total
---

# Cost Check

Run this any time you want to know where the project stands against its API
budget before triggering expensive work, or after a run that felt heavy. It
reads directly from the `invocation_log` table — the same source `BudgetGuard`
uses at call time — so the numbers are authoritative. For automated enforcement
(raising before a call goes out), see `templates/cost_guard.py`.

> The queries below assume SQLite. Adjust `date()` and `strftime()` calls for
> Postgres (`current_date`, `date_trunc`, `extract`). Set `DB` to your database
> path or connection string.

## Workflow

### 1. Set the database path

```bash
DB="${DONNA_DB:-donna_tasks.db}"
```

### 2. Today's total spend

```bash
sqlite3 "$DB" "
SELECT printf('Today  \$%.4f', COALESCE(SUM(cost_usd), 0.0))
FROM invocation_log
WHERE date(timestamp) = date('now');
"
```

### 3. Today's per-task-type breakdown

```bash
sqlite3 -column -header "$DB" "
SELECT
  task_type,
  COUNT(*)                              AS calls,
  SUM(tokens_in)                        AS tok_in,
  SUM(tokens_out)                       AS tok_out,
  printf('\$%.4f', SUM(cost_usd))       AS cost
FROM invocation_log
WHERE date(timestamp) = date('now')
GROUP BY task_type
ORDER BY SUM(cost_usd) DESC;
"
```

### 4. Month-to-date total

```bash
sqlite3 "$DB" "
SELECT printf('Month-to-date  \$%.4f', COALESCE(SUM(cost_usd), 0.0))
FROM invocation_log
WHERE timestamp >= date('now', 'start of month');
"
```

### 5. Month-to-date per-model breakdown

```bash
sqlite3 -column -header "$DB" "
SELECT
  model_alias,
  COUNT(*)                              AS calls,
  printf('\$%.4f', SUM(cost_usd))       AS cost
FROM invocation_log
WHERE timestamp >= date('now', 'start of month')
GROUP BY model_alias
ORDER BY SUM(cost_usd) DESC;
"
```

### 6. 7-day rolling average and projected month-end

```bash
sqlite3 -column -header "$DB" "
SELECT
  printf('\$%.4f', avg_daily)                               AS avg_daily_7d,
  printf('\$%.4f', mtd + avg_daily * days_left)             AS projected_month_end
FROM (
  SELECT
    (SELECT COALESCE(SUM(cost_usd), 0.0)
       FROM invocation_log
      WHERE timestamp >= date('now', 'start of month'))     AS mtd,
    (SELECT COALESCE(SUM(cost_usd), 0.0) / 7.0
       FROM invocation_log
      WHERE timestamp >= date('now', '-6 days'))            AS avg_daily,
    (CAST(strftime('%d',
           date('now', 'start of month', '+1 month', '-1 day')) AS INTEGER)
     - CAST(strftime('%d', date('now')) AS INTEGER))        AS days_left
);
"
```

### 7. Read the thresholds and issue a verdict

Load `DAILY_LIMIT` and `MONTHLY_LIMIT` from your config (e.g.
`config/budget.yaml`). Compare the numbers above:

- **GREEN** — today < 80% daily AND month-to-date < 80% monthly AND projection < monthly
- **WARN** — today ≥ 80% daily OR month-to-date ≥ 90% monthly OR projection ≥ monthly
- **PAUSE** — today ≥ daily limit OR month-to-date ≥ monthly limit (`BudgetGuard` will be raising)

## Guardrails

- Do not run cost-heavy evals or multi-step agent chains if the verdict is WARN
  or PAUSE — escalate to the user first.
- If verdict is PAUSE, `BudgetGuard.check()` is already raising `BudgetPausedError`
  on every outbound call; confirm before overriding the threshold.

## Output

```
## Cost Check — <YYYY-MM-DD>

| Metric                   | Amount    | Limit     | %      |
|--------------------------|-----------|-----------|--------|
| Today                    | $X.XXXX   | $XX.XX    | XX%    |
| Month-to-date            | $XX.XX    | $XXX.XX   | XX%    |
| 7-day avg daily          | $X.XXXX   | —         | —      |
| Projected month-end      | $XX.XX    | $XXX.XX   | XX%    |

Top tasks today: <task_type ($X.XXXX), ...>
Top models MTD: <model_alias ($X.XXXX), ...>

Verdict: GREEN / WARN / PAUSE — <reason if not GREEN>
```
