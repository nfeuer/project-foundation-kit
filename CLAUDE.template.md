# <PROJECT NAME> — <one-line description>

> This is a template. Replace every `<...>` placeholder and delete guidance
> in block-quotes like this one. Keep it under ~200 lines — CLAUDE.md is loaded
> into every session's context, so every line costs tokens on every turn. Put
> detail in `docs/` and the canonical spec; keep this file to the rules an agent
> must never violate and the pointers it needs to find everything else.

## What This Is
<Two or three sentences: what the project does and who it's for. If the product
has a personality or voice, state it here so generated output matches.>

## Core Problem
<The user problem being solved. This is the "why" behind every design decision —
when a rule seems arbitrary, this is what justifies it.>

## Tech Stack
- **Language:** <e.g. Python 3.12+ / asyncio>
- **Data:** <primary datastore, migration tool>
- **External services:** <APIs, queues, LLM providers>
- **Deployment:** <how it ships>
- **Observability:** <logging + metrics + dashboards stack>

## Key Design Principles — Follow These Always
> These are the non-negotiables. Number them; keep each to a sentence or two.
> The examples below are the ones that generalized well from real projects —
> keep the ones that apply, cut the rest, add your own.

1. **Config over code.** Routing, feature flags, state transitions, prompt
   templates, and thresholds live in versioned config (YAML/JSON), not in
   application logic. Never hardcode them.
2. **Safety first, dial back later.** New autonomy starts constrained
   (draft-only, feature-branch-only, dry-run). Constraints are relaxed
   explicitly via config, never assumed.
3. **Structured logging at every decision point — for every process type.**
   Every significant operation (background job, batch stage, consumer, external
   call) logs outcome + duration; jobs log start/progress/terminal events; state
   transitions log from→to. See `docs/LOGGING_STANDARD.md`. <If LLM-backed:>
   every model call additionally logs task_type, model, tokens, cost, and
   output. No exceptions.
4. **One abstraction per external dependency.** All <LLM / payment / email> calls
   go through a single interface. Never call a provider SDK directly from
   feature code.
5. **Validate at the boundary.** Untrusted input (model output, webhooks, user
   text) is schema-validated before it's used. Reject and retry on mismatch.

## Directory Layout
> One line per top-level directory. This is the map an agent uses to find things.
- `<spec.md>` — **Canonical design document.** All architectural decisions trace
  back here. Cite `§` sections when introducing or changing design.
- `docs/` — Browsable documentation. Narrative is hand-written; API/config/schema
  reference is auto-generated (never edit generated pages by hand). See
  `docs/DOCS_STANDARD.md`.
- `config/` — Versioned config files.
- `src/<pkg>/` — Application source.
- `tests/` — Unit + integration tests.
- `fixtures/` — Version-controlled evaluation fixtures.
- `.claude/` — Skills, agents, and hooks (worktree isolation, autoformat).
- `.claude/kit.yaml` — **Project profile.** Declares this repo's toolchain
  commands and capability toggles; the kit's skills read from it. See
  `docs/PROFILE.md`.
- `docs/followups.md` — Deferred decisions, accepted drift, and cross-cutting
  follow-ups. Append here; don't let TODOs rot in code.
- `docs/solutions/` — Solved-problem patterns (`compound-learnings` skill).
  Grep here before debugging; write here after solving something non-obvious.
- `docs/decisions/` — Architecture Decision Records (`adr` skill).

## Budget / Limits (if applicable)
- <e.g. $100/month hard cap on the LLM API; $20/day pause threshold.>
- <How spend is tracked — table, dashboard.>

## Before You Start a Task
1. Read this file.
2. **Check the `using-the-kit` skill's trigger index.** The 1% rule applies:
   if there is even a 1% chance a kit skill or gate applies to what you are
   about to do, invoke it — a skill whose capability is off reports N/A in
   seconds. Check before acting, including before clarifying questions.
3. Grep `docs/solutions/` for the area you're touching (and any error text you
   are chasing) — someone may have already solved this. See `compound-learnings`.
4. For any design decision, consult `<spec.md>` and cite the relevant `§` in
   your PR description.
5. Identify which `docs/domain/*.md` (or equivalent) pages are relevant.
6. Check `config/` for any config your code should read from instead of
   hardcoding.
7. **Work in an isolated worktree, not on `main`** — see the `parallel-work`
   skill. Concurrent sessions must not share a tree.
8. Run the test suite before and after your changes.

## Conventions
> The mechanical rules that keep the codebase uniform. Adapt to your language.
- <Async everywhere / concurrency model.>
- Type hints (or types) on all public signatures.
- Structured logging via <structlog / your logger> — never `print()`.
- Schema/DB changes require a migration — never modify tables by hand.
- All state transitions go through the state machine (loaded from `<config>`).
- **No silent failures.** Every `try/except` that falls back to a default or
  degraded path must emit a `fallback_activated` log event (and notify the debug
  channel where wired). Never `contextlib.suppress(Exception)` a real error.
- **Never log secrets or PII** in structured fields — log references, not
  payloads. See `docs/PII_LOGGING_CHECKLIST.md`.
- **Commits** follow `type(scope): subject` (see `docs/COMMIT_CONVENTION.md`).
- **Non-obvious design choices** get an ADR (`adr` skill), not just a code comment.

## Documentation & Spec Sync
> This is what keeps docs, spec, and code from drifting apart. Keep it.
- Narrative docs are hand-written under `docs/`. Reference docs
  (`docs/reference/`, `docs/config/`, `docs/schemas/`) are **auto-generated** —
  never commit hand edits to them.
- Docstrings on every new module and public function (Args / Returns / Raises).
- **Any design work** — PR descriptions, commit messages, doc pages — cites
  `<spec.md>` with the relevant `§`.
- **Keep the spec in sync.** When a PR changes behavior, schema, routing, config
  contract, or an integration the spec describes, update the affected `§` in the
  same PR. If the spec update is genuinely out of scope, call it out in the PR
  body and log it in `docs/followups.md` so it's reconciled later rather than
  silently drifting.
- **Follow-ups log.** When you finish a unit of work, scan it for deferred
  decisions and accepted drift, and append them to `docs/followups.md`.

## Definition of Done
A change is done when: tests/lint/types are green locally (`pre-pr` skill),
new/changed code paths are tested and coverage didn't drop, any change to auth /
secrets / user input / external calls passed security review, docs affected by
the change are updated, the spec is cited (and updated or a follow-up logged), no
new silent-failure paths were introduced, and the PR's CI is green.
