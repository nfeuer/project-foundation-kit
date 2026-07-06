---
name: observability-check
description: Verify a change is observable before merge — structured logging at decision points, no silent failures, correlation context, and dashboards/alerts for new failure modes
cost: subagents
protects: "A change gets checked for the logging a 2am on-call responder would need, before it merges instead of after an outage."
requires: nothing
gate_key: observability_check
ci_job: none
---

# Observability Check

Run this on any change that adds a decision point, an external call, a fallback,
a background job, a consumer, a pipeline stage, or a state transition. The goal:
when this code misbehaves in production at 2am, the logs alone should tell you
what happened and why — without a redeploy to add logging. This applies to
**every process type, not just API/model calls** — the per-process event catalog
(jobs, consumers, pipelines, lifecycle, state machines, caches) is
`docs/LOGGING_STANDARD.md`; hold the change to the rows that apply. For a deeper
automated pass, dispatch the **observability-reviewer** agent; this skill is the
inline checklist.

> **Mode.** This gate runs per `gates.modes.observability_check` in `.claude/kit.yaml`:
> `enforce` — run, block on failure; `suggest` — surface it at the natural
> moment with the `protects:` sentence and cost class above, run only on
> acceptance, and record accept/decline in the gate ledger
> (`.claude/scratch/gate-ledger.md`, SPEC.md §8.2) — never skip silently;
> `off` — not offered. Key absent → derive from `gates.strictness` per the
> table in `docs/PROFILE.md`. (SPEC.md §4.1, §4.4)

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
async boundaries. New entry points bind context at the top — and **jobs,
consumers, and pipeline runs count as entry points**: they bind a
`run_id`/`job_id` that plays the same role, and it travels across any queue or
process boundary the work crosses.

### 4. Every significant operation logs outcome + duration
Not just external calls. Any operation that can be slow or can fail — an
API/model/DB call, a batch stage, a cache rebuild, a file export, a migration —
emits a paired `<name>_completed` / `<name>_failed` event with `duration_ms`
(the `log_operation` helper in `templates/logging_setup.py` makes the pair one
line). For metered calls, add tokens and cost; failed-but-billed attempts still
get a row so spend is never lost.

### 4b. Long-running processes are legible while running, not just after
A job or pipeline that runs for minutes emits `job_started`, periodic
`job_progress` (items done / total), and a terminal event with items
processed / skipped / failed — a start event with no terminal event makes every
hang look like a crash. Skipped records log a `record_skipped` with a reason:
counts without reasons aren't replayable. State transitions log
`from_state` / `to_state` / trigger.

### 5. New failure modes are alertable
If the change introduces a new way to fail (a new background loop, a new
integration), there's a path for it to reach a human: a dashboard panel, an
alert rule, or at minimum an `event_type` that an existing error-explorer
dashboard already surfaces. Background tasks are supervised — an unexpected exit
logs and alerts, it doesn't die quietly. For scheduled work, remember the
inverse failure: a job that stops *being scheduled* emits nothing — the absence
of its `job_completed` heartbeat must be what alerts
(`templates/healthwatch.py`).

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
- Correlation context (incl. job/run ids): <flows / missing at ...>
- Operation telemetry (outcome + duration, all ops): <complete / missing at ...>
- Long-running process legibility (start/progress/terminal, skip reasons): <yes / gaps: ... / N/A>
- New failure modes alertable (incl. missing-heartbeat): <yes / add panel|alert for ...>
- PII & logging hygiene: <clean / issues: ...>
- Verdict: PASS / FIX NEEDED — <items>
```
