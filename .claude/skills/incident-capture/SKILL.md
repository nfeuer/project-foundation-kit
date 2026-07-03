---
name: incident-capture
description: When a component fires fallback_activated (or crashes) repeatedly in a window, auto-open a pre-filled incident note so the 2am page starts with context instead of a blank page.
---

# Incident Capture

**Profile-driven.** Alert destination is `alerts.channel` / `alerts.target` in `.claude/kit.yaml`. The SQLite fallback queries below use the table named by `capabilities.llm.spend_table` (default: `invocation_log`); substitute if your project differs.

A single `fallback_activated` event is expected; three in fifteen minutes is an
incident. This skill detects the repetition pattern, gathers the correlated log
context and the recent commits touching the component, writes an incident note
from `templates/incident_note.template.md`, and posts a summary to chat. The
person who picks up the page gets a filled-in timeline instead of a blank
document. See the `observability-check` skill for the logging conventions this
depends on, and `templates/fallback_alert.py` for the `fallback_activated` event
contract and the `FallbackNotifier` dedup mechanism.

## Workflow

### 1. Detect the trigger
Define "repeated" as N occurrences of the same `event_type` for the same
`component` within a rolling window. Sensible defaults: N = 3, window = 15 m.
Query Loki, the local structured log table, or the SQLite invocation log —
whichever is available:

```bash
# Loki (LogQL) — adapt label selectors to your stack
logcli query \
  '{app="donna"} |= "fallback_activated" | json | component="<component>"' \
  --since=15m --output=jsonl \
  | jq -s 'length'

# SQLite fallback — table: capabilities.llm.spend_table (kit.yaml)
sqlite3 donna_tasks.db "
  SELECT COUNT(*) FROM invocation_log
  WHERE event_type = 'fallback_activated'
    AND component  = '<component>'
    AND created_at >= datetime('now', '-15 minutes');"
```

If the count is below the threshold, exit 0 — nothing to open.

### 2. Deduplicate — one open incident per component
Before writing a new note, check whether an incident for this component is
already active. A sentinel file naming convention keeps the check simple:

```bash
mkdir -p docs/incidents/
ls docs/incidents/ 2>/dev/null | grep -q "^${component}-.*-open\.md$" && exit 0
```

This prevents a flapping component from generating a new note on every poll
cycle. When the existing incident is resolved, rename the file (swap `-open.md`
for `-resolved.md`) to re-arm the trigger.

### 3. Gather correlated log context
Pull the log lines for the window — include `correlation_id`, the error, and
the fallback taken. These become the "Correlated logs" section of the note:

```bash
logcli query \
  '{app="donna"} |= "fallback_activated" | json | component="<component>"' \
  --since=15m --output=jsonl \
  | jq -r '"\(.ts)  [\(.correlation_id // "no-id")]  \(.error)  → fallback: \(.fallback)"' \
  | head -20

# SQLite fallback — table: capabilities.llm.spend_table (kit.yaml)
sqlite3 -csv donna_tasks.db "
  SELECT created_at, correlation_id, error, fallback
  FROM   invocation_log
  WHERE  event_type = 'fallback_activated'
    AND  component  = '<component>'
    AND  created_at >= datetime('now', '-15 minutes')
  ORDER  BY created_at;" | head -20
```

### 4. Find the last commits touching the component
```bash
# Replace the path with the actual module and config locations
git log --oneline -10 -- "src/<pkg>/<component>/" "config/<component>*.yaml"
```

If the component last changed within the same git session, it is the primary
suspect. These hashes go into the "Related commits" section of the note.

### 5. Write the incident note from the template
```bash
component="<component>"
slug="${component}-$(date -u +%Y%m%d-%H%M%S)-open"
note="docs/incidents/${slug}.md"

# Populate with envsubst, sed, or a project helper; the template uses
# <PLACEHOLDER> markers — see templates/incident_note.template.md.
INCIDENT_COMPONENT="$component" \
INCIDENT_COUNT="$count"         \
INCIDENT_WINDOW="15m"           \
INCIDENT_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  envsubst < templates/incident_note.template.md > "$note"

git add "$note"
git commit -m "incident: open ${component} $(date -u +%Y-%m-%d)"
```

Commit on `main` (ops notes) or a short-lived branch — whichever your project
allows. Log a follow-up ID in `docs/followups.md` via the `followup-tracking`
skill if the incident uncovers deferred work.

### 6. Post to chat
Send a brief alert to the debug/ops channel with a direct link to the note:

```bash
# kit.yaml → alerts.channel / alerts.target (destination; swap URL/payload for Slack)
curl -sX POST "$DISCORD_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n \
    --arg msg "**Incident opened** · \`${component}\` fired \`fallback_activated\` ${count}× in ${window}
→ \`${note}\`" \
    '{content: $msg}')"
```

If the post fails, log the failure and continue — the note on disk is the
source of truth. Never let a broken notifier prevent the note from being written.

## Output
```
## Incident Capture
- Component:    <name>
- Trigger:      <event_type> × <count> in <window>
- Note:         docs/incidents/<slug>-open.md
- Correlation IDs: <list>
- Related commits: <short hashes + subjects | none in window>
- Chat notified: yes | failed (<reason>)
- Deduped:      no — new note created | yes — existing open incident, skipped
```
