# Logging Standard — every process, not just model calls

The kit's logging rules are often introduced through the LLM examples (tokens,
cost, task_type), but the discipline applies to **every process the system
runs**: request handlers, background jobs, queue consumers, batch pipelines,
state machines, and the process lifecycle itself. This page is the event
catalog that `observability-check` and the `observability-reviewer` agent
enforce. The reference implementation is `templates/logging_setup.py` (see
`log_operation` for the generic timing pattern) and `templates/fallback_alert.py`
for the no-silent-failure pattern.

## The three universal rules

1. **Every significant operation logs outcome + duration.** Not just external
   calls — a batch stage, a file export, a cache rebuild, a DB migration. If it
   can be slow or can fail, it emits `<name>_completed` / `<name>_failed` with
   `duration_ms`. The 2am question is "what ran, did it work, how long did it
   take" — for *everything* that ran.
2. **Every decision is replayable from its fields.** A route chosen, a retry
   scheduled, a record skipped, a threshold crossed — the event carries the
   inputs that drove the decision, not just the conclusion.
3. **Correlation context flows everywhere work flows.** Requests bind
   `correlation_id` at entry; **so do jobs, consumers, and pipeline runs**
   (a `run_id` / `job_id` serves the same role). If work crosses a process or
   queue boundary, the ID travels with it.

## Event catalog by process type

Field lists are the **minimum**; add whatever else makes the decision or
outcome replayable. Event names are snake_case tokens; high-value events also
carry a namespaced `event_type` the pipeline can index.

### Requests / interactions (API handler, bot command, UI action)

| Event | Required fields |
|---|---|
| `request_received` | `correlation_id`, `user_id`/`channel`, route/intent |
| `request_completed` / `request_failed` | `duration_ms`, status/outcome, error class on failure |

### External calls — HTTP, DB, email, webhook, *and* LLM

| Event | Required fields |
|---|---|
| `<service>_call_completed` / `_failed` | target/operation, `duration_ms`, outcome; retries so far |
| metered calls additionally | tokens, cost, model/task_type — **failed-but-billed attempts still get a row** |

### Background jobs & scheduled tasks (cron, nightly audits, sweeps)

| Event | Required fields |
|---|---|
| `job_started` | `job_id`/`run_id`, job name, trigger (cron/manual/event) |
| `job_progress` (long jobs, every N items or T seconds) | items done / total, current phase |
| `job_completed` / `job_failed` | `duration_ms`, items processed / skipped / failed, next scheduled run if known |
| `job_overlap_detected` | prior run still active — never start a second copy silently |

A job that logs only on failure is invisible when it silently stops being
scheduled — the *absence* of `job_completed` is the alert condition
(`templates/healthwatch.py` is the heartbeat companion).

### Queue / stream consumers (workers, event handlers)

| Event | Required fields |
|---|---|
| `message_processing_completed` / `_failed` | message/event id, `duration_ms`, attempt number |
| `message_retry_scheduled` | attempt, backoff delay, reason |
| `message_dead_lettered` | attempts exhausted, final error — this one alerts |
| `queue_depth_sampled` (periodic) | depth, consumer lag |

### Batch pipelines / ETL stages

| Event | Required fields |
|---|---|
| `stage_completed` / `stage_failed` | stage name, `run_id`, rows in / rows out, `duration_ms` |
| `record_skipped` | record ref, reason — skips are decisions; a count alone hides *why* |
| `pipeline_completed` | per-stage summary, total in/out — in≠out without logged skips is a bug |

### Process lifecycle

| Event | Required fields |
|---|---|
| `process_started` | version/commit, config summary (non-secret), enabled capabilities |
| `process_shutdown` | signal/reason, graceful vs forced, in-flight work drained or abandoned |
| `background_task_exited` | task name, expected vs unexpected — unexpected exits alert (supervised, never quiet) |

### State machines / transitions

| Event | Required fields |
|---|---|
| `state_transitioned` | entity id, `from_state`, `to_state`, trigger/reason |
| `transition_rejected` | entity id, attempted transition, why it was invalid |

### Retries, fallbacks, degraded paths

| Event | Required fields |
|---|---|
| `retry_scheduled` | operation, attempt, delay, error class |
| `fallback_activated` | what failed, what the fallback is, impact — **always** (see `templates/fallback_alert.py`) |
| `degraded_mode_entered` / `_exited` | which capability, why — the exit event matters as much as the entry |

### Caches & resource pools

| Event | Required fields |
|---|---|
| `cache_rebuilt` / `cache_invalidated` | cache name, entries, `duration_ms`, trigger |
| `pool_exhausted` | pool name, size, waiters — this one alerts |

(Per-lookup hit/miss belongs in metrics, not logs — log the *decisions*:
rebuilds, invalidations, exhaustion.)

## Anti-patterns

- **Failure-only logging.** A process that logs nothing on success can't be
  distinguished from a process that never ran.
- **Start without end.** `job_started` with no terminal event means every hang
  looks identical to a crash. Pair them; the `log_operation` helper makes the
  pair one line.
- **Counts without reasons.** "3 records skipped" is not replayable; three
  `record_skipped` events with reasons are.
- **Prose events.** `logger.info("Finished processing the nightly batch")` —
  ungreppable, unaggregatable. `log.info("job_completed", job="nightly_batch", ...)`.
- **Secrets/PII in fields.** Applies to every process type above — see
  `docs/PII_LOGGING_CHECKLIST.md`.
