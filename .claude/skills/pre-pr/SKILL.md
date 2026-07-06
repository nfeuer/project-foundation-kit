---
name: pre-pr
description: Run the full pre-PR gate — lint, types, tests, migration heads, docs, spec citations, follow-ups — so CI passes on first push instead of going red
cost: subagents
protects: "A pull request that would fail CI on lint, types, tests, migrations, security, docs, or spec drift gets caught and fixed locally, so it arrives green instead of blocking the queue."
requires: nothing
gate_key: lint_types_tests
ci_job: "lint, typecheck, test"
---

# Pre-PR Gate

Run this **before every `gh pr create`**, from inside the worktree you did the
work in. Its job is to catch everything CI would catch, locally, so no PR arrives
red and blocks the queue for other agents.

This gate runs in **two phases** (SPEC.md §6.2). **Phase 1** is the enforce-mode
set — it mirrors CI and always runs; a failure blocks, you fix and re-run,
exactly as before. **Phase 2** is a *consented menu*: the suggest-mode gates
your diff triggers, surfaced once for a human to run, pick, or skip — never run
silently, never skipped silently (§2.6). Every Phase-1 check mirrors a CI job —
keep the two in lockstep: when you add a CI job, add a Phase-1 step here.

The frontmatter `cost: subagents` prices **Phase 2** — Phase 1 is cheap and
deterministic; the subagent and live-model spend lives in the menu you accept
(SPEC.md §3's two-phase pricing). The report says which phase ran.

## Read the mode map first

Before anything else, read each gate's mode from `.claude/kit.yaml`:

```bash
# kit.yaml → gates.modes.<gate_key>
scripts/kit-config.sh get gates.modes.security_review    # → enforce | suggest | off
```

or read the `gates.modes:` block directly. A gate's mode decides its phase:
**enforce** → Phase 1 (runs; blocks on failure); **suggest** → Phase 2 (offered
in the menu); **off** → not run. **Key absent → derive from `gates.strictness`
per the table in `docs/PROFILE.md`** (the one fallback; init normally writes
every key). A skill this gate invokes by name that isn't installed is treated
exactly as `mode: off` — collapsed to one summary line, never an error (§5
pruning safety).

**Profile-driven.** Commands and capability gates below read from `.claude/kit.yaml`.
Each step tagged `# kit.yaml → <key>` runs the command at that key if set; an
empty string in the profile means skip the step and mark it N/A in the output.

**Strictness-aware.** At `prototype`, the trend gates — coverage ratchet, perf
budget, prompt-regression pass-gates — report their numbers but do not block;
they resolve to `suggest` and surface in the Phase-2 menu with `(advisory —
prototype)` on their line. `security_review` is **suggest-class** (subagent
cost): it rides the Phase-2 menu on the diffs that trigger it (§6.1). Only
`production` strictness sets it — and everything else installed — to `enforce`,
per the PROFILE.md table. Secrets scan and migrations are deterministic-
protective and block at every level.

## Phase 1 — Enforced gates (always run)

Create one todo per applicable step; work them in order. **Stop and fix** on any
failure before moving on — do not proceed to Phase 2, or report "ready," with a
known-red step. This is the enforce-mode set: the deterministic and CI-backed
steps below, **plus every other gate your mode map pins to `enforce`.** A
**docs-only diff** collapses Phase 1 to three steps (lint, secrets scan, working
tree) — say so in the report.

### 1. Lint
```bash
# kit.yaml → toolchain.lint
uv run ruff check src/ tests/
```
If it fails, run `uv run ruff check --fix src/ tests/` and re-run. The kit's
PostToolUse hook already auto-fixes on save, so this should usually be clean.

### 2. Types
```bash
# kit.yaml → toolchain.typecheck
uv run mypy src/
```

### 3. Tests
```bash
# kit.yaml → toolchain.test
uv run pytest tests/unit/ -m "not slow and not llm" --tb=short -q
```
If your change touches an integration surface, also run:
```bash
# kit.yaml → toolchain.test_integration
uv run pytest tests/integration/ -m "not slow and not llm" -q
```

### 4. Secrets scan
Run the **secret-scan-diff.sh** hook over the branch diff to catch keys/tokens
pasted into ordinary source files (the edit-time guard only covers credential
*files*). Any hit blocks the PR until removed and rotated. Deterministic-
protective: enforce at every level.

### 5. Migrations
**Applies when** `capabilities.migrations.enabled` is true. If false, skip and mark N/A.

```bash
# kit.yaml → capabilities.migrations.heads_cmd
uv run alembic heads   # expect exactly ONE head
```
Then run the **migration-check** skill — it catches destructive/irreversible ops
(dropped columns, non-nullable-without-default, narrowing) before they reach the
primary DB and any replica. More than one head means a merge migration is needed.

### 6. Build / typecheck any UI
**Applies when** `capabilities.ui.enabled` is true. If false, skip and mark N/A.

```bash
# kit.yaml → capabilities.ui.build_cmd
<ui-build-command>
```
```bash
# kit.yaml → capabilities.ui.typecheck_cmd
<ui-typecheck-command>
```
Run the frontend build and typecheck so a broken UI doesn't slip through.

### 7. Build artifact
**Applies when** `toolchain.build` is non-empty. If empty, skip and mark N/A.

```bash
# kit.yaml → toolchain.build
<build-command>
```

### 8. Coverage ratchet
**Applies when** `capabilities.coverage.ratchet_enabled` is true in `.claude/kit.yaml`.
If false, skip and mark N/A.

Run the **coverage-ratchet** skill to confirm the PR does not drop coverage below
the stored baseline (`.coverage-baseline`). A regression blocks the PR; an
accepted dip requires an updated baseline and a note in the follow-ups log. At
`prototype` this resolves to `suggest` — advisory, surfaced in the Phase-2 menu.

### 9. Performance budget
**Applies when** `capabilities.perf.enabled` is true. If false, skip and mark N/A.

Run the **perf-budget** skill to confirm no budgeted hot path or model call
regressed past its p95 tolerance versus the baseline. A regression blocks the PR;
an accepted change requires an updated `.perf-baseline` and a follow-up note. At
`prototype` this resolves to `suggest` — advisory, surfaced in the Phase-2 menu.

### 10. Prompt regression (if the change touches a prompt or model config)
Run the **prompt-regression** skill — re-run the affected task_type's eval
fixtures and confirm no gated tier regressed. An accepted score tradeoff must be
logged as a follow-up. Enforce when the `llm-app` preset pins it; at `prototype`
it drops to advisory and moves to the Phase-2 menu.

### 11. Branch-conflict check
Run the **branch-conflict-check** skill to see whether another open PR touches the
same files. If so, coordinate merge order before opening this one. Runs here when
`branch_conflict` is `enforce`; if your map sets it `suggest`, it appears in the
Phase-2 menu instead.

### 12. Working tree
```bash
git status --porcelain   # expect empty after commit
```

## Phase 2 — Suggest-mode menu (SPEC.md §6.2)

Once Phase 1 is green, compute the **trigger set** for the diff:

```bash
# kit.yaml → trunk_branch
git diff main...HEAD --name-only
```

Match the changed paths against the `gates.triggers.<gate_key>` globs in
`kit.yaml` (§6.1). Where a gate has no globs, fall back to agent judgment per
that gate's trigger sentence (documented fallback, not the mechanism).

Then **present ONE menu** at the natural moment — you MUST present it. An
unsurfaced suggestion is a silent skip, the kit's cardinal sin (§2.6); only the
human decides. List each *triggered* suggest-mode gate with its `protects:`
sentence and cost class, then the non-triggered-but-available ones under "Also
available":

> Enforced gates passed (lint, types, tests, secrets).
> Recommended for this diff: **security-review** (touched `src/auth/`),
> **doc-sync** (changed public API). Also available: test-gap.
> Run all / pick / skip — skips are recorded.

Run the accepted gates; append **every** accept and decline to the gate ledger
(below). The suggest-mode gates, with their triggers and content:

### Test coverage of the change — `test_gap` · cost: subagents
Dispatch the **test-gap-analyzer** agent to confirm new public functions and
changed branches have covering tests. A new untested code path is a blocking gap;
happy-path-only coverage of a risky path is a follow-up.

### Security review — `security_review` · cost: subagents
When the diff touches auth, secrets, user input validation, or external calls
(outbound HTTP, email, calendar, Discord) — or its `triggers` globs match —
dispatch the **security-reviewer** agent over the diff. It audits for credential
leaks, injection paths, auth bypass, and insecure token handling. An accepted
finding needs a documented reason. Suggest-class; `production` strictness sets it
to `enforce`, where it runs in Phase 1 on every diff.

### Docs sync — `docs_sync` · cost: subagents
Dispatch the **docs-updater** agent (or run the `doc-sync` skill) to update any
docs affected by the change. Narrative docs, changelog, and the API reference
must not drift from the code in the same PR.

### Spec + drift — `spec_drift` · cost: subagents
Dispatch the **spec-drift-checker** agent. Every design change must cite the
spec section it implements, and any behavior that diverges from the spec must
either update the spec in this PR or be logged in the follow-ups file with a
reason. If `capabilities.spec.file` is empty in `kit.yaml`, this gate is N/A.

### Follow-ups & learnings — `capture` · cost: free
Rides materiality, not every unit of work (§6.3): when the diff touched docs,
carries deferred decisions or accepted drift, or the work solved a non-obvious
problem. Scan the diff for TODOs, deferred decisions, and accepted drift; append
them to the follow-ups log (`doc-sync` skill / `docs/followups.md`) and close any
follow-up this PR resolves. If the work solved a hard problem, also run the
**compound-learnings** skill so the solution lands in `docs/solutions/`.

Trend gates (coverage ratchet, perf budget, prompt regression) that your map
resolves to `suggest` — e.g. under `prototype` — also appear in this menu rather
than Phase 1.

## The gate ledger (SPEC.md §8.2)

Every Phase-2 decision is appended to a **git-ignored, append-only, per-clone**
ledger at `.claude/scratch/gate-ledger.md` — one machine-readable line per event:

```
YYYY-MM-DD PR#<n> <gate_key> accepted|declined
```

Use the PR number when one exists, else the branch name. Examples:

```
2026-07-06 PR#12 security_review declined
2026-07-06 feat/auth-tokens test_gap accepted
```

Append on **every** accept and decline. These counters are personal and
per-clone; the committed mode map is team policy and changes only by PR. v2.1's
ratchet proposals count these lines — so record the declines too.

## Unattended sessions (SPEC.md §6.4)

A non-interactive session (cron, nightly-audit, pr-babysitter, headless CI)
cannot consent live. It runs **Phase 1 in full**; every Phase-2 gate is
**skip-and-logged** — a `not offered — unattended` line in the report, no ledger
entry — unless `gates.unattended.<gate_key>: run` in `kit.yaml` pre-consents it
(that is where the scheduling human's consent lives, §2.1). Never auto-accept a
suggestion.

## Output

Fill this in with real results — never check a box you didn't verify. Phase-1
`N/A` and `off` gates collapse to a single summary line, not one row each. State
which phases ran.

```
## Pre-PR Gate — Phase 1[ + Phase 2] ran

Phase 1 (enforced):
- [ ] Lint: <clean / N fixed>
- [ ] Types: <clean / errors>
- [ ] Tests: <XX passed>
- [ ] Integration tests: <XX passed / N/A>
- [ ] Secrets scan: <clean / BLOCKED — leak at ...>
- [ ] Migrations: <1 head, safe / N/A>
- [ ] UI build + types: <clean / N/A>
- [ ] Build: <clean / N/A>
- [ ] Coverage ratchet: <pass / dropped N% / advisory — prototype / N/A>
- [ ] Performance budget: <within budget / regressed <path> / N/A>
- [ ] Prompt regression: <no regression / N/A>
- [ ] Branch conflicts: <none / overlaps PR #N on <files>>
- [ ] Working tree: <clean>
Off / N/A: <one summary line — e.g. UI, build, replica: not configured>

Phase 2 (suggested — cost: subagents):
- Offered: <gate keys, or "none triggered">
- Accepted: <gate: result> ...
- Declined: <gate> ...  (recorded in .claude/scratch/gate-ledger.md)
- Not offered (unattended): <gate keys / n/a — interactive session>

Ready for PR: YES / NO — <blocking issues>
```
