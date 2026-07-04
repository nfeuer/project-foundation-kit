# Project Foundation Kit

A reusable starting point for new projects that bakes in the practices that are
painful to add late: **concurrent-agent isolation, observability, evaluation,
human-and-machine-readable logging, doc/spec/drift sync, follow-up tracking, and
a CI gate that agents keep green.**

Distilled from a production AI-assistant codebase where these patterns were
earned the hard way. It **adapts to the project**: a single profile
(`.claude/kit.yaml`) declares your toolchain and which capabilities apply, so the
same kit serves a Python LLM service and a Go CLI without editing every skill. It
works on **new and existing** repos alike.

## Install

**New project** — point Claude at this kit and invoke bootstrap:

```
/new-project-bootstrap
```

It detects your stack (manifests, CI, Makefile), picks an archetype **preset**,
writes `.claude/kit.yaml`, then installs the hooks, skills, agents, CLAUDE.md,
docs standard, follow-ups log, and CI.

**Existing project** — adopt non-destructively instead:

```
/adopt-existing-project
```

It audits what you already have, reports gaps ranked by leverage, and **merges**
kit pieces in (append to your settings, add only missing CI jobs, never clobber
your files) with a phased rollout you approve step by step.

After either, run `/kit-doctor` to confirm everything is wired correctly.

## What's inside

```
CLAUDE.template.md              Project-instructions template (the file loaded every session)
.claude/
  kit.yaml                      THE PROFILE — toolchain + capability toggles every skill reads
  settings.template.json        Hook wiring (portable via $CLAUDE_PROJECT_DIR)
  hooks/
    require-worktree.sh         Blocks edits on main → forces per-agent worktrees
    prune-merged-worktrees.sh   Auto-removes worktrees whose PR merged (careful safety rules)
    post-merge-prune.sh         Sweeps worktrees right after `gh pr merge`
    secret-scan-diff.sh         Blocks push/PR when a secret leaked into a source file
  skills/
    new-project-bootstrap/      Greenfield install: detect stack → write kit.yaml → scaffold
    adopt-existing-project/     Brownfield install: audit → gap report → non-destructive merge
    kit-doctor/                 Verify an install is correctly wired (never modifies)
    kit-update/                 Propagate source-kit improvements to an adopted project
    parallel-work/              Worktree isolation for concurrent Claude sessions
    pre-pr/                     Local gate mirroring CI — green locally = green PR
    ci-watch/                   Watch a PR's CI and fix failures until green
    branch-conflict-check/      Warn when another open PR touches the same files (+ check.sh)
    pr-babysitter/              Loop over the open-PR queue: rebase, re-run CI, ping on blockers
    migration-check/            Catch destructive/irreversible DB migrations before merge
    coverage-ratchet/           Fail a PR that drops coverage below the baseline (one-way floor)
    perf-budget/                Fail a PR that regresses a hot path past its p95 budget
    prompt-regression/          Re-run eval fixtures when a prompt/model change lands
    eval-harness/               Tiered, version-controlled fixtures for fuzzy behavior
    observability-check/        Verify a change is debuggable before merge
    doc-sync/                   Update docs + spec + follow-ups in the same PR
    adr/                        Record an Architecture Decision when a non-obvious choice is made
    followup-tracking/          Durable log for deferred work and accepted drift
    flaky-triage/               Confirm, log, and quarantine flaky tests (a visible loan)
    cost-check/                 Query spend vs daily/monthly budget + projection
    session-handoff/            Baton note so another session/agent can resume
    release/                    Conventional-commits → changelog + semver bump + tagged release
    nightly-audit/              Cron the drift/health checks → morning chat digest
    incident-capture/           Auto-open a pre-filled incident note on repeated fallbacks
    sync-health/                Verify a primary+replica aren't lagging or dropping rows
  agents/
    observability-reviewer.md   Audits a diff for silent failures + missing logging
    security-reviewer.md        Audits a diff for injection, auth bypass, credential/token leaks
    spec-drift-checker.md       Flags spec sections that drifted from the code
    docs-updater.md             Updates affected narrative docs for a branch
    test-gap-analyzer.md        Finds untested new/changed code paths, ranked by risk
    config-consistency-checker.md  Validates cross-file config refs all resolve
    dependency-auditor.md       Flags outdated/vulnerable deps across Python/Node/system
    codebase-onboarder.md       Generates an orientation doc for an unfamiliar repo
presets/                        Archetype starting profiles: library / service / llm-app / frontend / data-pipeline
docs/
  PROFILE.md                    How the kit.yaml profile works and how skills consume it
  PRESETS.md                    The five archetypes and how to pick one
  DOCS_STANDARD.md              Hand-written vs generated split + sync discipline
  COMMIT_CONVENTION.md          Conventional-commit format (feeds changelog automation)
  PII_LOGGING_CHECKLIST.md      What never to log; how to handle user data in structured logs
  followups.template.md         The follow-ups log format
templates/
  logging_setup.py              Structured logging: dual-render, correlation context
  fallback_alert.py             No-silent-failure fallback alerting
  cost_guard.py                 Pre-call budget guardrail (log-every-call, check-before-call)
  perf_budget.py                Runtime timing guard: alerts when an op blows its p95 budget
  healthwatch.py                Heartbeat + transition-alert health-watcher sidecar
  eval_fixture.example.json     The eval fixture shape
  incident_note.template.md     Fill-in incident write-up
  adr.template.md               Architecture Decision Record template
  flaky-tests.template.md       The quarantined-flaky-test registry
.github/
  workflows/kit-ci.yml          The kit's own CI (validates profile/skills/hooks/templates)
templates/ci.template.yml       Lint + types + tests gate that projects copy to .github/workflows/ci.yml
  pull_request_template.md      PR checklist: spec cite, test evidence, risk + rollback
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
(untested new paths, risk-ranked) · `coverage-ratchet` (coverage can't drop) ·
`perf-budget` (p95 can't regress) · `prompt-regression` (eval deltas on prompt/
model changes) · `security-reviewer` (injection, auth bypass, credential/token
leaks) · `config-consistency-checker` (dangling config refs) · `secret-scan-diff.sh`
(keys leaked into source) · `flaky-triage` (flaky tests confirmed + quarantined).

**Observability & evaluation** — make behavior debuggable and measurable.
`observability-check` + `observability-reviewer` (no silent failures, logging at
decision points) · `eval-harness` (tiered fixtures) · `cost-check` + `cost_guard.py`
(spend vs budget, pause-before-call) · `logging_setup.py` / `fallback_alert.py`
(the reference patterns).

**Docs, spec & memory** — stop drift and lost context.
`doc-sync` + `docs-updater` · `spec-drift-checker` · `adr` (decision records) ·
`followup-tracking` · `session-handoff` (baton note between sessions).

**Release & operations** — standing signals and clean releases.
`release` (conventional commits → changelog + semver + tag) · `nightly-audit`
(cron the drift/health checks → morning digest) · `incident-capture` (auto-open an
incident note on repeated fallbacks) · `sync-health` (primary+replica lag/parity) ·
`dependency-auditor` · `healthwatch.py` (heartbeat sidecar) · `codebase-onboarder`.

**Adapt & maintain the kit itself** — make it fit the project and stay current.
`new-project-bootstrap` / `adopt-existing-project` (greenfield vs brownfield
install) · the `kit.yaml` profile + `presets/` (one file drives the toolchain and
capability toggles every skill reads) · `kit-doctor` (verify the wiring) ·
`kit-update` (pull source-kit improvements without clobbering local changes).

## Adapting it — the profile

The kit's defaults read like a Python + `uv` + `ruff` + `mypy` + `pytest` +
`structlog` + `gh` project, but you never edit skills to change that. One file —
`.claude/kit.yaml` — declares the toolchain commands and capability toggles, and
every skill reads from it (see `docs/PROFILE.md`):

- **Toolchain commands** are tagged in each skill (`# kit.yaml → toolchain.test`).
  The literal shown is the default; the profile overrides it. An empty string
  means "skip that step." So a Node project sets `toolchain.test: "npm test"` once
  and `pre-pr`/`ci-watch` follow.
- **Capability toggles** gate whole skills. `capabilities.llm.enabled: false`
  drops the eval/prompt-regression/cost gates; `capabilities.migrations.enabled:
  false` drops migration-check — reported N/A, no edits.
- **Presets** (`presets/*.yaml`) are archetype starting points — `library`,
  `service`, `llm-app`, `frontend`, `data-pipeline` — so a new project inherits a
  sensible profile and only the skills that fit.

Bootstrap **detects** most of the profile from the repo; `adopt-existing-project`
**recovers** it from an existing repo's CI/Makefile rather than imposing defaults.
`kit-doctor` then confirms every profile command actually runs and every hook is
wired. The hooks are portable via `$CLAUDE_PROJECT_DIR` and degrade gracefully
(no `gh`/auth → they no-op rather than error).

## How this compares to other skills & workflow packages

Most popular Claude Code packages govern **how the agent works a single task**.
This kit governs **what the repo enforces around every task** — the hooks,
gates, harnesses, and templates that outlive any one session. That puts it at a
different layer from the packages you may already use, and makes it a companion
to most of them rather than a replacement.

### Pairs well with superpowers

[superpowers](https://github.com/obra/superpowers) is a per-task engineering
methodology: brainstorm a spec before any code, write a fine-grained plan,
enforce strict TDD, dispatch fresh subagents per task, review with evidence,
land the branch. It is excellent at disciplining *the agent* — and it
deliberately stops there. It doesn't install CI, detect your toolchain,
scaffold observability, run eval fixtures against prompt changes, ratchet
coverage, gate destructive migrations, or automate releases.

That's this kit's whole job, and the two compose cleanly:

- **superpowers** makes the agent brainstorm, plan, and test-drive its way
  through a task. **The kit** makes sure the resulting PR can't arrive red,
  can't drop coverage, can't regress a p95 budget or an eval score, and can't
  merge with silent fallbacks or drifted docs — no matter how the code was
  produced.
- The one real overlap is **worktree isolation and branch finishing**.
  superpowers practices it as an in-session workflow the agent follows; the kit
  installs it as a PreToolUse hook that *blocks* edits on `main` for every
  session — including ones where no methodology is loaded — plus
  merge-triggered cleanup. They agree on the pattern, so they don't fight.

If superpowers is a senior engineer sitting beside the agent for each task,
this kit is the CI, observability, and evaluation scaffolding the whole team's
repo runs on. Use both.

### The rest of the landscape

| Package | Layer it targets | Relationship to this kit |
|---|---|---|
| [SuperClaude](https://github.com/SuperClaude-Org/SuperClaude_Framework), [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) | Task methodology: lifecycle commands, personas, behavioral modes | Orthogonal — neither installs repo infrastructure (hooks, CI gates, eval, observability) |
| [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin) | Methodology plus a compounding-learnings loop | Nearest neighbor: it has worktrees, a CI-repair loop, and a `docs/solutions/` feedback step — but no eval/prompt-regression harness, observability templates, migration/coverage/perf gates, or toolchain profile |
| [Agent OS](https://github.com/buildermethods/agent-os) | Capturing your codebase's standards into reusable spec context | Complementary: standards documents vs. installed gates and harnesses; its any-stack claim is the closest analog to `kit.yaml` |
| [anthropics/skills](https://github.com/anthropics/skills), [claude-code-templates](https://github.com/davila7/claude-code-templates), [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | Skill-format reference, component marketplaces, discovery indexes | Parts bins and distribution channels — you assemble the pieces; the kit is a pre-assembled, opinionated system whose pieces reference each other |
| [claude-flow](https://github.com/ruvnet/claude-flow) | Multi-agent swarm orchestration, vector memory | Different problem entirely: agent coordination, not repo hygiene |

### What no other package bundles

1. **Enforced, not suggested.** Worktree isolation and secret scanning are
   hooks that block the action, not workflow steps the agent is asked to
   remember. Discipline that survives a fresh session with no context.
2. **One profile, any stack.** `kit.yaml` adapts every skill's commands and
   capability set to your toolchain from a single file. Methodology frameworks
   assume you know your commands; marketplaces make you pick per-language
   variants.
3. **LLM behavior is gated, not vibes.** Tiered eval fixtures, prompt-regression
   runs on prompt/model diffs, and cost guards with budget projection. No
   methodology framework ships a regression story for non-deterministic
   behavior.
4. **Observability as code.** Reference templates for structured dual-render
   logging, no-silent-failure fallback alerting, perf budgets, and health
   watching — plus a review gate that checks a diff is debuggable before merge.
5. **The PR queue is managed end to end.** A local gate that mirrors CI,
   CI-watching until green, conflict warnings across open PRs, coverage and
   perf ratchets, flaky-test quarantine, and release automation.
6. **Adoption is a lifecycle, not an install.** `adopt-existing-project` merges
   into brownfield repos non-destructively, `kit-doctor` verifies the wiring,
   and `kit-update` propagates upstream improvements without clobbering local
   changes.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, adapt it to your own projects.
