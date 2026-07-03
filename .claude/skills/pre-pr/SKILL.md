---
name: pre-pr
description: Run the full pre-PR gate — lint, types, tests, migration heads, docs, spec citations, follow-ups — so CI passes on first push instead of going red
---

# Pre-PR Gate

Run this **before every `gh pr create`**, from inside the worktree you did the
work in. Its job is to catch everything CI would catch, locally, so no PR arrives
red and blocks the queue for other agents. Every check mirrors a CI job — keep
the two in lockstep: when you add a CI job, add a step here.

> Adjust the commands below to your toolchain. The defaults assume a Python
> project using `uv` + `ruff` + `mypy` + `pytest` (see `.github/workflows/ci.yml`
> in the kit). For Node, substitute `npm run lint` / `tsc --noEmit` / `npm test`.

## Checklist

Create one todo per step, then work them in order. **Stop and fix** on any
failure before moving on — do not report "ready" with a known-red step.

### 1. Lint
```bash
uv run ruff check src/ tests/
```
If it fails, run `uv run ruff check --fix src/ tests/` and re-run. The kit's
PostToolUse hook already auto-fixes on save, so this should usually be clean.

### 2. Types
```bash
uv run mypy src/
```

### 3. Tests
```bash
uv run pytest tests/unit/ -m "not slow and not llm" --tb=short -q
```
If your change touches an integration surface, also run the relevant
`tests/integration/` subset.

### 4. Test coverage of the change
Dispatch the **test-gap-analyzer** agent to confirm new public functions and
changed branches have covering tests. A new untested code path is a blocking gap;
happy-path-only coverage of a risky path is a follow-up.

### 5. Migrations (if the project uses DB migrations)
```bash
uv run alembic heads   # expect exactly ONE head
```
Then run the **migration-check** skill — it catches destructive/irreversible ops
(dropped columns, non-nullable-without-default, narrowing) before they reach the
primary DB and any replica. More than one head means a merge migration is needed.

### 6. Build / typecheck any UI (if applicable)
Run the frontend build + typecheck so a broken UI doesn't slip through.

### 7. Secrets scan
Run the **secret-scan-diff.sh** hook over the branch diff to catch keys/tokens
pasted into ordinary source files (the edit-time guard only covers credential
*files*). Any hit blocks the PR until removed and rotated.

### 8. Docs sync
Dispatch the **docs-updater** agent (or run the `doc-sync` skill) to update any
docs affected by the change. Narrative docs, changelog, and the API reference
must not drift from the code in the same PR.

### 9. Spec + drift
Run the **spec-check** skill (or dispatch **spec-drift-checker**). Every design
change must cite the spec section it implements, and any behavior that diverges
from the spec must either update the spec in this PR or be logged in the
follow-ups file with a reason.

### 10. Prompt regression (if the change touches a prompt or model config)
Run the **prompt-regression** skill — re-run the affected task_type's eval
fixtures and confirm no gated tier regressed. An accepted score tradeoff must be
logged as a follow-up.

### 11. Follow-ups
Scan your diff for TODOs, deferred decisions, and accepted drift. Append them to
the follow-ups log (`doc-sync` skill / `docs/followups.md`). Close any follow-up
this PR resolves.

### 12. Branch-conflict check
Run the **branch-conflict-check** skill to see whether another open PR touches the
same files. If so, coordinate merge order before opening this one.

### 13. Working tree
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
- [ ] Test coverage: <no gaps / N new untested paths>
- [ ] Migrations: <1 head, safe / N/A>
- [ ] UI build + types: <clean / N/A>
- [ ] Secrets scan: <clean / BLOCKED — leak at ...>
- [ ] Docs: <updated <files> / no docs affected>
- [ ] Spec: <cited §X.Y / §X.Y may need update — reason / N/A>
- [ ] Prompt regression: <no regression / N/A>
- [ ] Follow-ups: <none / added N / closed N>
- [ ] Branch conflicts: <none / overlaps PR #N on <files>>
- [ ] Working tree: <clean>

Ready for PR: YES / NO — <blocking issues>
```
