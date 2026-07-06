---
name: sync-health
description: For a primary + replica setup, verify replication isn't lagging or silently dropping rows — the data-integrity drift that's invisible until the numbers don't match.
cost: cheap
protects: "Replication drift between a primary and its replica — lagging writes or silently dropped rows — gets caught and alerted on before the data has quietly diverged for hours."
requires: "capabilities.replica.enabled with primary and replica connections configured"
gate_key: sync_health
ci_job: none
---

# Sync Health

**Profile-driven.** Reads `capabilities.replica` keys from `.claude/kit.yaml`. Alert destination is `alerts.channel` / `alerts.target`. The skill is **skipped entirely** (`N/A`) when `capabilities.replica.enabled` is false — safe to leave installed on projects that have no replica.

> **Mode.** This gate runs per `gates.modes.sync_health` in `.claude/kit.yaml`:
> `enforce` — run, block on failure; `suggest` — surface it at the natural
> moment with the `protects:` sentence and cost class above, run only on
> acceptance, and record accept/decline in the gate ledger
> (`.claude/scratch/gate-ledger.md`, SPEC.md §8.2) — never skip silently;
> `off` — not offered. Key absent → derive from `gates.strictness` per the
> table in `docs/PROFILE.md`. (SPEC.md §4.1, §4.4)

Write-through replication from a primary to a replica (e.g. SQLite → Postgres) can
drift silently: a failed sync worker, a schema mismatch, or a burst of writes that
outpaces the commit rate leaves rows missing on the replica with no visible error on
the primary. By the time a query notices, the drift may span hours. This skill runs
structured lag and parity checks across the tables the project cares about, spot-checks
field-level equality on recent records, and verifies the sync worker's own heartbeat —
then fires a `fallback_activated`-style alert and opens an incident note the moment
drift exceeds the configured thresholds. The alert pattern mirrors `healthwatch.py`:
a state-transition alert fires on first breach and again on recovery; a sustained
lag does not flood the channel.

Schedule it via `/schedule` so it runs alongside nightly-audit, or invoke manually
before a release. See the `incident-capture` skill for the incident-note format this
skill triggers, and the `nightly-audit` skill for how its summary section folds into
the morning digest.

**Ships DISABLED by default** (`capabilities.replica.enabled: false`). The `service`
and `data-pipeline` presets flip it to `true`.

## Profile keys

The coordinator adds the following keys to `.claude/kit.yaml` when enabling this skill.
All are nested under `capabilities.replica`:

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `capabilities.replica.enabled` | bool | `false` | Gates the entire skill; `false` → skip/N/A |
| `capabilities.replica.primary` | string | — | Human label or DSN for the primary (e.g. `sqlite:///donna_tasks.db`) |
| `capabilities.replica.replica` | string | — | Human label or DSN for the replica (e.g. `postgres://…`) |
| `capabilities.replica.tables` | list | — | Tables to check for lag and parity (e.g. `[tasks, invocation_log]`) |
| `capabilities.replica.lag_threshold_s` | int | `300` | Alert when newest-row lag exceeds this many seconds |
| `capabilities.replica.parity_tolerance` | int | `0` | Alert when replica row count differs from primary by more than this |

Example stanza:

```yaml
# kit.yaml
capabilities:
  replica:
    enabled: true
    primary:  "sqlite:///donna_tasks.db"
    replica:  "postgres://user:pass@host/donna"
    tables:
      - tasks
      - invocation_log
    lag_threshold_s: 300      # 5 minutes
    parity_tolerance: 0       # exact parity required
```

## Workflow

### 1. Capability gate

**Applies when `capabilities.replica.enabled` is true.** If false, report `N/A` for
every section and exit 0 — do not query any database.

### 2. Register or invoke the scheduled run

Wire the agent to a cron that complements the nightly-audit schedule via `/schedule`:

```
/schedule "sync-health" --cron "*/15 * * * *"
```

For a finer polling cadence (e.g. every 15 minutes), schedule independently of
nightly-audit. For a once-per-night check, fold this skill into nightly-audit's step 7
by invoking it before assembling the digest. For a one-off run, execute the steps below
directly.

### 3. Measure replication lag per table

For each table in `capabilities.replica.tables`, find the `MAX(created_at)` (or the
project's equivalent timestamp column) on both primary and replica. The difference is
the per-table lag in seconds.

```bash
# kit.yaml → capabilities.replica.tables
# Repeat for each table; substitute your timestamp column name.

# Primary (SQLite example)
primary_max=$(sqlite3 donna_tasks.db \
  "SELECT strftime('%s','now') - strftime('%s', MAX(created_at))
   FROM tasks;")

# Replica (Postgres example)
replica_max=$(psql "$REPLICA_DSN" -tAc \
  "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at)))::int
   FROM tasks;")

lag=$(( primary_max - replica_max ))
echo "tasks lag: ${lag}s"
```

**Guardrail:** if either query fails (connection refused, table missing), treat it as
infinite lag — do not silently skip. Log `event_type="sync_health.query_failed"` with
the table name and error, then continue to the next table so all results are collected
before alerting.

### 4. Check row-count parity

For each table compare `COUNT(*)` on primary vs. replica. A difference beyond
`capabilities.replica.parity_tolerance` is a parity breach.

```bash
# kit.yaml → capabilities.replica.tables, capabilities.replica.parity_tolerance

# Primary
primary_count=$(sqlite3 donna_tasks.db "SELECT COUNT(*) FROM tasks;")

# Replica
replica_count=$(psql "$REPLICA_DSN" -tAc "SELECT COUNT(*) FROM tasks;")

delta=$(( primary_count - replica_count ))
echo "tasks parity: primary=${primary_count} replica=${replica_count} delta=${delta}"
```

Track both the absolute delta and the direction (primary ahead vs. replica ahead — the
latter is unexpected and should be flagged separately as a potential write-bypass).

### 5. Spot-check field-level equality

Sample the 5 most-recently modified rows that exist on both sides and compare a key
field (primary key + one business field) for exact equality. This is not a full
reconciliation scan — it catches serialization bugs and partial writes that row counts
miss.

```bash
# Pull the 5 most-recent IDs from the primary
ids=$(sqlite3 donna_tasks.db \
  "SELECT id FROM tasks ORDER BY created_at DESC LIMIT 5;" | paste -sd,)

# Compare a stable field (e.g. status) on replica
psql "$REPLICA_DSN" -tAc \
  "SELECT id, status FROM tasks WHERE id IN (${ids}) ORDER BY id;" \
  > /tmp/replica_sample.txt

sqlite3 donna_tasks.db \
  "SELECT id, status FROM tasks WHERE id IN (${ids}) ORDER BY id;" \
  > /tmp/primary_sample.txt

diff /tmp/primary_sample.txt /tmp/replica_sample.txt \
  && echo "spot-check: PASS" \
  || echo "spot-check: MISMATCH — field-level drift detected"
```

Log any mismatch with `event_type="sync_health.field_mismatch"` and the differing row
IDs. A field mismatch is treated as a parity breach for alerting purposes regardless of
`parity_tolerance`.

### 6. Check the sync worker heartbeat

Verify the sync worker wrote a recent heartbeat. The heartbeat file follows the same
atomic-rename pattern as `templates/healthwatch.py`.

```bash
# kit.yaml → (project-specific; adapt path and threshold)
heartbeat="/run/donna/sync_worker.heartbeat"
age=$(python3 -c "
import datetime, pathlib, sys
p = pathlib.Path('${heartbeat}')
if not p.exists(): sys.exit(1)
ts = datetime.datetime.fromisoformat(p.read_text().strip())
age = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds()
print(int(age))
" 2>/dev/null)

if [[ $? -ne 0 ]]; then
  echo "sync worker heartbeat: MISSING"
else
  echo "sync worker heartbeat: ${age}s ago"
fi
```

A missing or stale heartbeat (age > `capabilities.replica.lag_threshold_s`) is treated
as a lag breach — the worker may have crashed or stalled before flushing rows to the
replica.

### 7. Evaluate thresholds and alert

Collect all per-table results. If any table exceeds `capabilities.replica.lag_threshold_s`
in lag, or exceeds `capabilities.replica.parity_tolerance` in row-count delta, or has a
field-level mismatch, or the sync worker heartbeat is missing/stale:

1. Log `event_type="fallback_activated"` with `component="sync_health"`, the breaching
   table(s), the measured values, and the thresholds.
2. Post an alert to `alerts.channel` / `alerts.target`:

```bash
# kit.yaml → alerts.channel (discord | slack | none), alerts.target
curl -sX POST "$DISCORD_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n \
    --arg msg "**sync-health breach** · replica lag or parity exceeded threshold
Tables: ${breaching_tables}
Worst lag: ${worst_lag}s (threshold: ${lag_threshold_s}s)
Parity delta: ${worst_delta} rows (tolerance: ${parity_tolerance})
→ opening incident" \
    '{content: $msg}')"
```

3. Invoke the `incident-capture` skill with `component="sync_health"` to open an
   incident note under `docs/incidents/`.

**Transition-alert, not poll-alert.** Fire the alert only when state changes (clean →
breaching or breaching → recovered), not on every poll cycle. A sustained breach
produces exactly two alerts: the initial breach and the recovery. Track state in a
sentinel file:

```bash
sentinel="/tmp/sync_health.breach"
if [[ "$breach" == "true" ]] && [[ ! -f "$sentinel" ]]; then
  touch "$sentinel"
  # send alert + open incident
elif [[ "$breach" == "false" ]] && [[ -f "$sentinel" ]]; then
  rm "$sentinel"
  # send recovery alert
fi
```

**Guardrail:** if the alert post fails, log the failure with
`event_type="sync_health.alert_dispatch_failed"` and continue — the incident note on
disk is the source of truth. Never let a broken notifier prevent the breach from being
recorded.

### 8. Fold into nightly-audit digest

The nightly-audit skill's step 7 (assemble digest) includes a `Sync` section drawn from
this skill's output. Pass the per-table summary as an argument to
`scripts/build_audit_digest.py` alongside spec-drift and dependency findings. Omit the
section entirely when all tables are clean and the worker heartbeat is fresh.

## Output

```
## Sync Health — <YYYY-MM-DD HH:MM UTC>
Primary:    <primary label>
Replica:    <replica label>

Table              Lag (s)   Parity delta   Spot-check
tasks              12        0              PASS
invocation_log     8         0              PASS

Worker heartbeat:  <Ns ago | MISSING>
Threshold:         lag > <lag_threshold_s>s  or  delta > <parity_tolerance> rows

Result:            CLEAN | BREACH
Breach tables:     <table list | none>
Alert sent:        yes | no (state unchanged) | failed (<reason>)
Incident opened:   <docs/incidents/<slug>-open.md | none>
```
