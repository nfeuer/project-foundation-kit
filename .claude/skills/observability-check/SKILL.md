---
name: observability-check
description: Verify a change is observable before merge — structured logging at decision points, no silent failures, correlation context, and dashboards/alerts for new failure modes
---

# Observability Check

Run this on any change that adds a decision point, an external call, a fallback,
or a background task. The goal: when this code misbehaves in production at 2am,
the logs alone should tell you what happened and why — without a redeploy to add
logging. For a deeper automated pass, dispatch the **observability-reviewer**
agent; this skill is the inline checklist.

## What to check

### 1. Decision points are logged
Every branch that matters — a route chosen, a threshold crossed, a retry, a
degraded path taken — emits a structured event with enough context to replay the
decision. Event names are snake_case (`route_selected`, `budget_exceeded`), not
prose. High-value events carry a namespaced `event_type` your pipeline can index.

### 2. No silent failures
Grep the diff for swallowed errors:
```bash
git diff main...HEAD | grep -nE 'except.*:\s*(pass|return|continue)|suppress\(Exception\)'
```
Every `try/except` that falls back must emit `event_type="fallback_activated"`
(see `templates/fallback_alert.py`). A bare `except: pass` is a bug.

### 3. Correlation context flows
The change sets/propagates `correlation_id` (and `user_id`, `task_id` where
relevant) so a single request's logs can be stitched together across modules and
async boundaries. New entry points bind context at the top.

### 4. External calls log latency + outcome
Every call to an API/model/DB logs whether it succeeded, how long it took, and —
for metered calls — tokens and cost. Failed-but-billed attempts still get a row
so spend is never lost.

### 5. New failure modes are alertable
If the change introduces a new way to fail (a new background loop, a new
integration), there's a path for it to reach a human: a dashboard panel, an
alert rule, or at minimum an `event_type` that an existing error-explorer
dashboard already surfaces. Background tasks are supervised — an unexpected exit
logs and alerts, it doesn't die quietly.

### 6. Logs are human-readable too
Field names are what a human would grep for. The console renderer (dev mode)
produces a line an engineer can scan; the JSON renderer (prod) produces the same
fields for the pipeline. Don't log opaque blobs or stringified dicts where
structured fields belong.

### 7. PII & logging hygiene
Never log secrets, API tokens, or PII (names, email addresses, phone numbers,
message content) in structured log fields. Redact or omit user-supplied content
before it reaches the logging layer. Temporary debug fields must be removed
before merge; respect the project's retention policy for any fields that do
land in persistent storage. See `docs/PII_LOGGING_CHECKLIST.md` for the full
checklist.

## Output
```
## Observability Review
- Decision points logged: <yes / gaps: ...>
- Silent failures: <none / found at file:line>
- Correlation context: <flows / missing at ...>
- External-call telemetry: <complete / missing latency|cost at ...>
- New failure modes alertable: <yes / add panel|alert for ...>
- PII & logging hygiene: <clean / issues: ...>
- Verdict: PASS / FIX NEEDED — <items>
```
