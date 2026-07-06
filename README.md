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
    protect-credential-files.sh Refuses agent edits to .env/keys/credential files
    autoformat.sh               Formats the just-edited file (per-extension, best-effort)
    prune-merged-worktrees.sh   Auto-removes worktrees whose PR merged (careful safety rules)
    post-merge-prune.sh         Sweeps worktrees right after `gh pr merge`
    secret-scan-diff.sh         Blocks push/PR when a secret leaked into a source file
                                (hooks read stdin JSON, degrade loudly, and are
                                behaviorally tested in kit-ci — they must BLOCK in tests)
  skills/
    new-project-bootstrap/      Greenfield install: detect stack → write kit.yaml → scaffold
    adopt-existing-project/     Brownfield install: audit → gap report → non-destructive merge
    kit-doctor/                 Verify an install is correctly wired (never modifies)
    kit-update/                 Propagate source-kit improvements to an adopted project
    using-the-kit/              The dispatcher: 1%-rule trigger index + red-flags table
    writing-kit-skills/         Author a kit-compatible skill (extend, don't fork)
    config-audit/               Security audit of settings/hooks/CLAUDE.md/MCP configs
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
    logging-init/               Probe → 3 questions → wire structured logging for any stack
    doc-sync/                   Update docs + spec + follow-ups in the same PR
    adr/                        Record an Architecture Decision when a non-obvious choice is made
    followup-tracking/          Durable log for deferred work and accepted drift
    compound-learnings/         Write solved-problem patterns to docs/solutions/
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
  PROGRESS_LEDGER.md            Resumable step-state for long kit operations
  DOCS_STANDARD.md              Hand-written vs generated split + sync discipline
  LOGGING_STANDARD.md           Event catalog per process type — jobs, consumers, pipelines, lifecycle, not just API calls
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
8. **Solved problems compound.** Non-obvious fixes are written to
   `docs/solutions/` and re-read before planning and debugging, so each unit of
   work makes the next one easier — and skills chain into each other at natural
   moments (pre-pr → ci-watch → capture), while the enforce class is carried by
   hooks that block regardless of session context.

## The workflow catalog

Every workflow below ships in the kit, priced by its worst-case cost class (SPEC.md §3).

<!-- catalog:begin -->
_Generated from skill frontmatter by `scripts/gen-catalog.sh` — edit the skills' frontmatter, not this table (kit-ci fails on drift)._

### Gates (mode-mapped via `gates.modes.<gate key>`)

| Skill | Protects | Cost | Requires | Gate key | CI job |
|---|---|---|---|---|---|
| branch-conflict-check | You find out which other open pull requests touch the same files as yours before you merge, instead of hitting the conflict by surprise afterward. | cheap | GitHub CLI (gh) authenticated | `branch_conflict` | — |
| compound-learnings | A hard-won fix to a tricky bug gets written down once, so the next person starts from the answer instead of repeating the same investigation. | free | capabilities.docs.enabled | `capture` | — |
| coverage-ratchet | Test coverage can only hold steady or improve — a drop below the recorded baseline is caught and blocked instead of quietly eroding over time. | cheap | capabilities.coverage.ratchet_enabled; a recorded coverage baseline | `coverage_ratchet` | — |
| doc-sync | Docs and the canonical spec stay in step with the code change in the same pull request, instead of drifting silently over time. | subagents | capabilities.docs.enabled | `docs_sync` | — |
| flaky-triage | A test that turns red then green gets confirmed as flaky, logged, and optionally quarantined instead of silently blocking or being ignored. | cheap | — | `flaky_triage` | — |
| followup-tracking | Decisions you deferred and gaps you accepted get written down in one durable place instead of disappearing in a merged pull request. | free | capabilities.docs.enabled | `capture` | — |
| migration-check | A database migration that would break production or a replica — multiple heads, a fake rollback, an unguarded destructive change — gets caught before it ships. | cheap | capabilities.migrations.enabled | `migration_check` | — |
| observability-check | A change gets checked for the logging a 2am on-call responder would need, before it merges instead of after an outage. | subagents | — | `observability_check` | — |
| parallel-work | Concurrent agents working in the same repo can't overwrite or corrupt each other's changes, because each stream of work gets its own isolated branch and worktree. | cheap | — | `worktree_isolation` | — |
| perf-budget | Hot-path and model-call latency regressions get caught before they reach production, instead of showing up as a slower app for real users. | cheap | capabilities.perf.enabled; a latency source — invocation_log (SUBSTRATE.md §1) or a benchmark_cmd | `perf_budget` | — |
| pre-pr | A pull request that would fail CI on lint, types, tests, migrations, security, docs, or spec drift gets caught and fixed locally, so it arrives green instead of blocking the queue. | subagents | — | `lint_types_tests` | lint, typecheck, test |
| prompt-regression | Prompt or model changes ship with a before/after eval score instead of a vibe. | subagents | eval fixtures + a runner (SUBSTRATE.md §2); capabilities.llm.enabled | `prompt_regression` | — |
| sync-health | Replication drift between a primary and its replica — lagging writes or silently dropped rows — gets caught and alerted on before the data has quietly diverged for hours. | cheap | capabilities.replica.enabled with primary and replica connections configured | `sync_health` | — |

### Workflows & conventions (never mode-gated)

| Skill | Protects | Cost | Requires |
|---|---|---|---|
| adopt-existing-project | The kit's guardrails get added to a repo already in flight without overwriting anything you wrote, and every change is shown as a diff you approve before it's applied. | cheap | — |
| adr | The reasoning behind a hard design choice gets written down, including the alternatives you rejected, so no one has to guess or re-argue it later. | free | — |
| ci-watch | A pull request's CI run gets watched until it finishes, and any failure gets diagnosed and fixed automatically instead of being left red. | cheap | GitHub CLI (gh) authenticated |
| config-audit | The files that steer the agent — settings, hooks, CLAUDE.md, skills, MCP configs — get checked for leaked secrets and hidden instructions before you commit them. | free | — |
| cost-check | You see today's and this month's API spend against budget, with a projected month-end total, before you kick off expensive work. | cheap | invocation_log spend table (SUBSTRATE.md §1); capabilities.llm.enabled |
| eval-harness | Changes to a prompt, model, or classifier get scored against version-controlled test cases before they ship, so a quality regression is caught instead of shipping on a vibe. | subagents | eval fixtures + a runner (SUBSTRATE.md §2); capabilities.llm.enabled |
| incident-capture | A repeating failure automatically opens an incident note with the timeline already filled in, so whoever responds starts with context instead of a blank page. | cheap | invocation_log (SUBSTRATE.md §1); alert transport (SUBSTRATE.md §3) |
| kit-doctor | Broken wiring in the installed kit — a hook that can't fire, a missing tool, a bad config — gets caught before it costs you a failed run. | cheap | — |
| kit-update | Improvements from the source kit reach an adopted project without silently overwriting anything the team customized. | cheap | a source-kit checkout on disk |
| logging-init | Scattered print statements or an ad-hoc logger get upgraded to structured logging with correlation context and timing, without breaking what already works. | cheap | — |
| new-project-bootstrap | A new project starts with the safety nets teams usually add too late — isolated work, logging that never fails silently, and a CI gate that stays green. | cheap | — |
| nightly-audit | Docs, spec, dependencies, and follow-ups get checked every morning and only the problems worth acting on reach chat, instead of drift piling up unnoticed. | subagents | a scheduler (SUBSTRATE.md §4); alert transport (SUBSTRATE.md §3) |
| pr-babysitter | Stale-but-green pull requests stay mergeable and the queue keeps moving, without a human having to manually rebase and re-check every PR. | cheap | GitHub CLI (gh) authenticated; a scheduler for loop mode (SUBSTRATE.md §4) |
| release | Cutting a release produces an accurate versioned changelog and tag straight from what actually merged, instead of a hand-written changelog that drifts from reality. | cheap | GitHub CLI (gh) authenticated |
| session-handoff | Work in progress survives a context switch or handoff, because what's done, what's next, and why gets written down before it would otherwise be lost. | free | — |
| using-the-kit | The right safeguard actually runs at the moment it matters, instead of being silently skipped because nobody remembered it existed. | free | — |
| writing-kit-skills | A newly written skill actually gets discovered and triggered when it's needed, instead of becoming dead documentation nobody invokes. | free | — |
<!-- catalog:end -->

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
- **Gate strictness** (`gates.strictness`) scales ceremony to maturity by
  selecting the default `gates.modes:` map init writes into `kit.yaml`:
  `prototype` demotes the trend gates (coverage / perf / eval) to suggest while
  the deterministic-protective gates (secrets, credential files, migrations)
  stay enforce; `production` sets everything installed to enforce. Strictness
  only picks the defaults — any line in the map can be overridden (SPEC.md §4.4).
  See `docs/PROFILE.md`.
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

1. **Enforced where it's deterministic and catastrophic; consented-and-recorded
   everywhere else.** Hooks still block secret leaks and credential-file edits —
   and, where enabled, edits outside a worktree — without asking; judgment-based
   gates are offered with their cost and outcome, and every decline is recorded
   rather than silently skipped.
2. **One profile, any stack.** `kit.yaml` adapts every skill's commands and
   capability set to your toolchain from a single file. Methodology frameworks
   assume you know your commands; marketplaces make you pick per-language
   variants.
3. **LLM behavior is gated where you turn it on — and the llm-app preset turns
   it on by default.** Tiered eval fixtures, prompt-regression runs on
   prompt/model diffs, and cost guards with budget projection. No methodology
   framework ships a regression story for non-deterministic behavior.
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

Credit where due: several conventions here were borrowed deliberately after
studying the neighbors. The 1%-rule skill dispatcher (`using-the-kit`) and the
skill-authoring meta-skill (`writing-kit-skills`) adapt superpowers' best
mechanics; the `compound-learnings` loop adapts compound-engineering's
solved-problems step; the config security audit (`config-audit`) was inspired
by everything-claude-code's AgentShield. The kit's job is to bundle the
repo-infrastructure layer well, not to pretend every good idea originated here.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, adapt it to your own projects.
