---
name: pre-pr
description: Run the full pre-PR gate — lint, types, tests, migration heads, docs, spec citations, follow-ups — so CI passes on first push instead of going red
---

# Pre-PR Gate

Run this **before every `gh pr create`**, from inside the worktree you did the
work in. Its job is to catch everything CI would catch, locally, so no PR arrives
red and blocks the queue for other agents. Every check mirrors a CI job — keep
the two in lockstep: when you add a CI job, add a step here.

**Profile-driven.** Commands and capability gates below read from `.claude/kit.yaml`.
Each step tagged `# kit.yaml → <key>` runs the command at that key if set; an
empty string in the profile means skip the step and mark it N/A in the output.

## Checklist

Create one todo per step, then work them in order. **Stop and fix** on any
failure before moving on — do not report "ready" with a known-red step.

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

### 4. Test coverage of the change
Dispatch the **test-gap-analyzer** agent to confirm new public functions and
changed branches have covering tests. A new untested code path is a blocking gap;
happy-path-only coverage of a risky path is a follow-up.

### 5. Security review
If the change touches auth, secrets, user input validation, or external calls
(outbound HTTP, email, calendar, Discord), dispatch the **security-reviewer**
agent over the diff. It audits for credential leaks, injection paths, auth bypass,
and insecure token handling. Any finding blocks the PR until addressed or
explicitly accepted with a documented reason. If none of those surfaces are
involved, mark N/A.

### 6. Coverage ratchet
**Applies when** `capabilities.coverage.ratchet_enabled` is true in `.claude/kit.yaml`.
If false, skip and mark N/A.

Run the **coverage-ratchet** skill to confirm the PR does not drop coverage below
the stored baseline (`.coverage-baseline`). A regression blocks the PR; an
accepted dip requires an updated baseline and a note in the follow-ups log.

### 7. Performance budget
**Applies when** `capabilities.perf.enabled` is true. If false, skip and mark N/A.

Run the **perf-budget** skill to confirm no budgeted hot path or model call
regressed past its p95 tolerance versus the baseline. A regression blocks the PR;
an accepted change requires an updated `.perf-baseline` and a follow-up note.

### 8. Migrations
**Applies when** `capabilities.migrations.enabled` is true. If false, skip and mark N/A.

```bash
# kit.yaml → capabilities.migrations.heads_cmd
uv run alembic heads   # expect exactly ONE head
```
Then run the **migration-check** skill — it catches destructive/irreversible ops
(dropped columns, non-nullable-without-default, narrowing) before they reach the
primary DB and any replica. More than one head means a merge migration is needed.

### 9. Build / typecheck any UI
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

### 10. Build artifact
**Applies when** `toolchain.build` is non-empty. If empty, skip and mark N/A.

```bash
# kit.yaml → toolchain.build
<build-command>
```

### 11. Secrets scan
Run the **secret-scan-diff.sh** hook over the branch diff to catch keys/tokens
pasted into ordinary source files (the edit-time guard only covers credential
*files*). Any hit blocks the PR until removed and rotated.

### 12. Docs sync
Dispatch the **docs-updater** agent (or run the `doc-sync` skill) to update any
docs affected by the change. Narrative docs, changelog, and the API reference
must not drift from the code in the same PR.

### 13. Spec + drift
Run the **spec-check** skill (or dispatch **spec-drift-checker**). Every design
change must cite the spec section it implements, and any behavior that diverges
from the spec must either update the spec in this PR or be logged in the
follow-ups file with a reason.

### 14. Prompt regression (if the change touches a prompt or model config)
Run the **prompt-regression** skill — re-run the affected task_type's eval
fixtures and confirm no gated tier regressed. An accepted score tradeoff must be
logged as a follow-up.

### 15. Follow-ups
Scan your diff for TODOs, deferred decisions, and accepted drift. Append them to
the follow-ups log (`doc-sync` skill / `docs/followups.md`). Close any follow-up
this PR resolves.

### 16. Branch-conflict check
Run the **branch-conflict-check** skill to see whether another open PR touches the
same files. If so, coordinate merge order before opening this one.

### 17. Working tree
```bash
git status --porcelain   # expect empty after commit
```

## Output

Fill this in with real results — never check a box you didn't verify. Mark
conditional gates `N/A` when they don't apply:

```
## Pre-PR Gate

- [ ] Lint: <clean / N fixed>
- [ ] Types: <clean / errors>
- [ ] Tests: <XX passed>
- [ ] Integration tests: <XX passed / N/A>
- [ ] Test coverage: <no gaps / N new untested paths>
- [ ] Security review: <clean / N findings addressed / N/A>
- [ ] Coverage ratchet: <pass / dropped N% below baseline / N/A>
- [ ] Performance budget: <within budget / regressed <path> / N/A>
- [ ] Migrations: <1 head, safe / N/A>
- [ ] UI build + types: <clean / N/A>
- [ ] Build: <clean / N/A>
- [ ] Secrets scan: <clean / BLOCKED — leak at ...>
- [ ] Docs: <updated <files> / no docs affected>
- [ ] Spec: <cited §X.Y / §X.Y may need update — reason / N/A>
- [ ] Prompt regression: <no regression / N/A>
- [ ] Follow-ups: <none / added N / closed N>
- [ ] Branch conflicts: <none / overlaps PR #N on <files>>
- [ ] Working tree: <clean>

Ready for PR: YES / NO — <blocking issues>
```
