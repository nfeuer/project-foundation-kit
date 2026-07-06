---
name: logging-init
description: Initialize or upgrade structured logging in a project — probe what already exists, ask 2–3 targeted questions, recommend a stack-mapped setup per docs/LOGGING_STANDARD.md, and wire it with approval, migrating rather than replacing what's there. Run during bootstrap/adoption, or whenever a repo is logging with print/console.log or an ad-hoc logger.
cost: cheap
protects: "Scattered print statements or an ad-hoc logger get upgraded to structured logging with correlation context and timing, without breaking what already works."
requires: nothing
gate_key: none
ci_job: none
---

# Logging Init

Logging is the practice that hurts most when added late — by the time a repo
has a hundred `print()` calls, every debugging session pays for the missing
structure. But wiring a logging *library* isn't the goal; wiring the
**capabilities** in `docs/LOGGING_STANDARD.md` is: one processor chain with
two renderers, correlation context that flows, snake_case events, and
outcome + duration on every significant operation. This skill gets a repo
there from any starting point — greenfield, print-statements, or an
established logger that just lacks structure — without ripping out anything
the team already relies on.

**Invoked from** `new-project-bootstrap` step 8 and `adopt-existing-project`
Phase 4; also run it standalone whenever the probe below would find print-only
or ad-hoc logging. Nothing is written until step 5's approval.

## Workflow

### 1. Probe what exists (read-only)

Let the repo answer before recommending anything. Detect the language from
`.claude/kit.yaml`'s toolchain (or manifests if no profile yet), then:

```bash
# Known logging libraries — imports/requires per language
grep -rEl --include='*.py'  'import (structlog|loguru)|import logging' src/ 2>/dev/null | head
grep -rEl --include='*.{js,ts}' "require\(['\"](pino|winston|bunyan)|from ['\"](pino|winston)" src/ lib/ 2>/dev/null | head
grep -rEl --include='*.go'  '"log/slog"|"go.uber.org/zap"|"github.com/rs/zerolog"' . 2>/dev/null | head
grep -rEl --include='*.rs'  'tracing::|log::' src/ 2>/dev/null | head

# Logging config files
ls logging.conf logging.yaml log4rs.yaml pino.config.* 2>/dev/null

# Unstructured-logging density — the honest signal of the starting point
grep -rE --include='*.py' '^\s*print\(' src/ 2>/dev/null | wc -l
grep -rE --include='*.{js,ts}' 'console\.(log|error|warn)' src/ lib/ 2>/dev/null | wc -l
```

Add `--exclude-dir={.git,.venv,node_modules,__pycache__,dist,build,.claude}`
to every grep. Also check whether an existing setup already has the standard's
capabilities: dual renderers, context vars / correlation binding, a timing
helper. Record findings — they drive everything below.

### 2. Classify the starting point

| Evidence | Classification | Posture |
|---|---|---|
| No logging imports; zero or few prints | **GREENFIELD** | Install the full reference setup |
| Prints / `console.log` as the de-facto logger | **PRINT-ONLY** | Install full setup + log a migration follow-up for call sites |
| Stdlib logging or scattered ad-hoc use, no structure | **PARTIAL** | Add structure around what exists; don't break existing handlers |
| Established structured library (structlog, pino, zap, tracing…) | **ESTABLISHED** | Keep the library; add only the missing capabilities as adapters |

### 3. Ask the targeted questions — one batch, detected defaults

Ask the user these **in a single batch**, each pre-filled with the detected
default so answering is cheap. Do not ask anything the probe already answered.

1. **Destination** — where do prod logs go? (`stdout` for a collector to
   scrape — the default and usually right; a file; or direct shipping to
   Loki / Datadog / CloudWatch.) Detected hint: existing handler/transport
   config, a `promtail`/`fluent-bit`/agent config in the repo or its deploy
   files.
2. **Dev rendering** — human-readable console lines locally and JSON in prod
   (default: switch on TTY), or JSON everywhere?
3. **Correlation unit** — what identifies one unit of work to stitch logs
   together: a request id (from which framework/header?), a job/run id, a
   message id? This decides where `bind_request_context` (or equivalent) gets
   called. Detected hint: web framework middleware, queue consumers, cron
   entry points found in step 1.

If the session is non-interactive and no answer arrives, proceed with the
detected defaults, mark each assumed answer clearly in the output block, and
append a follow-up (`followup-tracking`) so the assumptions get confirmed —
never let a default silently become policy.

### 4. Recommend — stack-mapped, standard-driven

The recommendation is the LOGGING_STANDARD capabilities mapped onto the
detected language. Reference libraries:

| Language | Recommended | Notes |
|---|---|---|
| Python | `structlog` | Port `templates/logging_setup.py` nearly as-is |
| Node/TS | `pino` | `pino-pretty` for the dev renderer; `AsyncLocalStorage` for context |
| Go | `log/slog` (stdlib) | `slog.NewJSONHandler` / text handler; context via `slog` attrs + `context.Context` |
| Rust | `tracing` | `tracing-subscriber` with JSON + pretty layers; spans are the correlation mechanism |
| Browser/frontend | keep `console` in dev | structure goes to the error/telemetry reporter, not the console; log *events*, ship via the app's reporting layer |

Whatever the language, the recommendation names the same four capabilities and
how each maps: (1) one config, two renderers; (2) correlation context bound at
every entry point — requests, jobs, consumers; (3) snake_case event naming with
`event_type`; (4) a `log_operation`-style outcome+duration helper. For
**ESTABLISHED** repos, present this as a gap list against their current setup
("pino present; missing: context propagation, timing helper") — the library
stays.

### 5. Wire it — with approval, additively

Show the plan (files to add/modify, packages to install) and get explicit
approval before writing. Then:

- **GREENFIELD / PRINT-ONLY:** add the logging module (ported from
  `templates/logging_setup.py`), call setup at each process entry point,
  bind correlation context at the entry points identified in Q3, and wire
  `templates/fallback_alert.py` if alerts are configured. For PRINT-ONLY,
  migrate only the entry-point files now; log a follow-up for the remaining
  call sites — a wholesale rewrite is review-hostile and not this skill's job.
- **PARTIAL / ESTABLISHED:** additive only. Never remove existing handlers or
  rewrite existing call sites without per-file approval. Add the missing
  capabilities as a thin module the existing logger plugs into.
- Record the decisions in `.claude/kit.yaml` so skills and future runs know
  the state:
  ```yaml
  # kit.yaml → logging.*
  logging:
    initialized: true
    library: "structlog"       # what step 4 landed on
    destination: "stdout"      # Q1 answer
    dev_console: true          # Q2 answer
  ```
- Update CLAUDE.md's Tech Stack → Observability line and principle 3 so every
  future session knows the logging contract.

### 6. Verify

- Import/run the setup module; confirm dev rendering on a TTY and JSON when
  piped (`... | head -1 | python3 -m json.tool` or equivalent).
- Emit one test event through the full chain and check every configured field
  (timestamp, level, correlation id) appears in both renderings.
- Run the **observability-check** skill over the diff before it merges.

## Output

```
## Logging Init

- Starting point: GREENFIELD | PRINT-ONLY (N sites) | PARTIAL | ESTABLISHED (<library>)
- Existing capabilities found: <dual-render / context / timing helper / none>
- Answers: destination=<stdout|…> dev_console=<yes|no> correlation=<request|job|message via …>
  (<answered by user | assumed defaults — follow-up logged>)
- Recommendation: <library> + <capabilities added>
- Wired: <files added/modified / dry-run — awaiting approval>
- kit.yaml logging block: <written / unchanged>
- Migration follow-up: <ID for remaining print/console sites / none needed>
- Verified: <dev+JSON render OK, test event fields OK / not yet>
```
