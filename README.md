# Project Foundation Kit

A reusable starting point for new projects that bakes in the practices that are
painful to add late: **concurrent-agent isolation, observability, evaluation,
human-and-machine-readable logging, doc/spec/drift sync, follow-up tracking, and
a CI gate that agents keep green.**

Distilled from a production AI-assistant codebase where these patterns were
earned the hard way. Drop it into a new repo with the `new-project-bootstrap`
skill and you start on a strong foundation instead of retrofitting one.

## Install

Point Claude at this kit and invoke the bootstrap skill:

```
/new-project-bootstrap
```

It copies the hooks, skills, agents, CLAUDE.md, docs standard, follow-ups log,
and CI into the target repo, then walks you through filling in the placeholders.
Or copy pieces by hand — everything is standalone.

## What's inside

```
CLAUDE.template.md              Project-instructions template (the file loaded every session)
.claude/
  settings.template.json        Hook wiring (portable via $CLAUDE_PROJECT_DIR)
  hooks/
    require-worktree.sh         Blocks edits on main → forces per-agent worktrees
    prune-merged-worktrees.sh   Auto-removes worktrees whose PR merged (careful safety rules)
    post-merge-prune.sh         Sweeps worktrees right after `gh pr merge`
    secret-scan-diff.sh         Blocks push/PR when a secret leaked into a source file
  skills/
    new-project-bootstrap/      Install this kit into a repo
    parallel-work/              Worktree isolation for concurrent Claude sessions
    pre-pr/                     Local gate mirroring CI — green locally = green PR
    ci-watch/                   Watch a PR's CI and fix failures until green
    branch-conflict-check/      Warn when another open PR touches the same files (+ check.sh)
    pr-babysitter/              Loop over the open-PR queue: rebase, re-run CI, ping on blockers
    migration-check/            Catch destructive/irreversible DB migrations before merge
    test-gap → see agents       (test-gap-analyzer agent, gated from pre-pr)
    prompt-regression/          Re-run eval fixtures when a prompt/model change lands
    eval-harness/               Tiered, version-controlled fixtures for fuzzy behavior
    observability-check/        Verify a change is debuggable before merge
    doc-sync/                   Update docs + spec + follow-ups in the same PR
    followup-tracking/          Durable log for deferred work and accepted drift
    cost-check/                 Query spend vs daily/monthly budget + projection
    session-handoff/            Baton note so another session/agent can resume
    nightly-audit/              Cron the drift/health checks → morning chat digest
    incident-capture/           Auto-open a pre-filled incident note on repeated fallbacks
  agents/
    observability-reviewer.md   Audits a diff for silent failures + missing logging
    spec-drift-checker.md       Flags spec sections that drifted from the code
    docs-updater.md             Updates affected narrative docs for a branch
    test-gap-analyzer.md        Finds untested new/changed code paths, ranked by risk
    config-consistency-checker.md  Validates cross-file config refs all resolve
    dependency-auditor.md       Flags outdated/vulnerable deps across Python/Node/system
    codebase-onboarder.md       Generates an orientation doc for an unfamiliar repo
docs/
  DOCS_STANDARD.md              Hand-written vs generated split + sync discipline
  followups.template.md         The follow-ups log format
templates/
  logging_setup.py              Structured logging: dual-render, correlation context
  fallback_alert.py             No-silent-failure fallback alerting
  cost_guard.py                 Pre-call budget guardrail (log-every-call, check-before-call)
  healthwatch.py                Heartbeat + transition-alert health-watcher sidecar
  eval_fixture.example.json     The eval fixture shape
  incident_note.template.md     Fill-in incident write-up
.github/workflows/ci.template.yml   Lint + types + tests gate
```

## The core ideas

1. **No two agents on `main`.** Every stream of work gets its own branch in its
   own git worktree. A PreToolUse hook enforces it; a merge-triggered hook cleans
   up after. Two Claude instances can run at once without crossing wires.
2. **CI never goes red on arrival.** The `pre-pr` gate mirrors every CI job
   locally; `ci-watch` catches the environment-specific failures that slip
   through and fixes them until green.
3. **No silent failures.** Every fallback is logged (`fallback_activated`) and,
   where wired, alerted. `contextlib.suppress(Exception)` is banned.
4. **Logs serve both readers.** One processor chain renders JSON for the pipeline
   and a clean console line for a human debugging locally — same fields either way.
5. **Docs, spec, and code move together.** A change updates its docs, cites (and
   where in scope, updates) the spec, and logs any accepted drift — in the same
   PR. Drift is tracked, never silent.
6. **Deferred work is durable.** Follow-ups go in a greppable log with stable
   IDs, not code comments that vanish at merge.
7. **Fuzzy behavior has a regression suite.** Tiered, version-controlled eval
   fixtures with pass-gates, run offline with mocked tools, gated in CI.

## The workflow catalog by purpose

Every workflow below ships in the kit. Grouped by the problem it solves:

**Concurrency & the PR queue** — keep a fleet of agents from colliding.
`parallel-work` (worktree isolation) · `branch-conflict-check` (warn when two
open PRs touch the same files) · `pr-babysitter` (rebase/re-run/ping the open-PR
queue without auto-merging) · `pre-pr` + `ci-watch` (green locally, kept green).

**Quality gates** — catch expensive mistakes before merge.
`migration-check` (destructive/irreversible schema ops) · `test-gap-analyzer`
(untested new paths, risk-ranked) · `prompt-regression` (eval deltas on prompt/
model changes) · `config-consistency-checker` (dangling config refs) ·
`secret-scan-diff.sh` (keys leaked into source, blocks push/PR).

**Observability & evaluation** — make behavior debuggable and measurable.
`observability-check` + `observability-reviewer` (no silent failures, logging at
decision points) · `eval-harness` (tiered fixtures) · `cost-check` + `cost_guard.py`
(spend vs budget, pause-before-call) · `logging_setup.py` / `fallback_alert.py`
(the reference patterns).

**Docs, spec & memory** — stop drift and lost context.
`doc-sync` + `docs-updater` · `spec-drift-checker` · `followup-tracking` ·
`session-handoff` (baton note between sessions).

**Operations & safety** — standing signals, not one-off checks.
`nightly-audit` (cron the drift/health checks → morning digest) ·
`incident-capture` (auto-open an incident note on repeated fallbacks) ·
`dependency-auditor` · `healthwatch.py` (heartbeat sidecar) · `codebase-onboarder`.

### Ideas not yet built (good next candidates)

- **Release / changelog automation** — assemble the changelog from merged PRs +
  their spec citations; tag and draft release notes.
- **Flaky-test quarantine** — track tests that pass on re-run with no code change;
  auto-file a follow-up and optionally quarantine until fixed.
- **Latency/performance budget** — flag when a hot path or model call regresses
  past a p95 threshold, the perf analogue of the cost guardrail.
- **Data/replica sync health** — for a primary + replica setup, verify the
  write-through sync isn't lagging or dropping rows.

## Adapting it

The defaults assume Python + `uv` + `ruff` + `mypy` + `pytest` + `structlog` +
GitHub + `gh`. Every piece is language-agnostic in intent — swap the concrete
commands (autoformat hook, CI steps, `pre-pr` steps, logging library) for your
stack. The hooks are portable across machines via `$CLAUDE_PROJECT_DIR`; they
degrade gracefully (no `gh`, no auth → they no-op rather than error).
