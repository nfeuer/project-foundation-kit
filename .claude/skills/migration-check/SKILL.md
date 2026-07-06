---
name: migration-check
description: Catch dangerous DB schema migrations before they hit the primary DB or any replica — verify single head, reversibility, and no unguarded destructive ops
cost: cheap
protects: "A database migration that would break production or a replica — multiple heads, a fake rollback, an unguarded destructive change — gets caught before it ships."
requires: "capabilities.migrations.enabled"
gate_key: migration_check
ci_job: none
---

# Migration Check

**Applies when** `capabilities.migrations.enabled` is true (else skip, report N/A).

**Profile-driven.** The migration tool command comes from `capabilities.migrations.heads_cmd` and the file-path glob from `capabilities.migrations.versions_glob` in `.claude/kit.yaml`; edit the profile to adapt to Flyway, Prisma, or any other tool.

> **Mode.** This gate runs per `gates.modes.migration_check` in `.claude/kit.yaml`:
> `enforce` — run, block on failure; `suggest` — surface it at the natural
> moment with the `protects:` sentence and cost class above, run only on
> acceptance, and record accept/decline in the gate ledger
> (`.claude/scratch/gate-ledger.md`, SPEC.md §8.2) — never skip silently;
> `off` — not offered. Key absent → derive from `gates.strictness` per the
> table in `docs/PROFILE.md`. (SPEC.md §4.1, §4.4)

Run this **as part of pre-pr** whenever a PR touches `*/versions/*` (Alembic) or
any equivalent migration directory. Its job is to stop a destructive or
un-reversible migration from reaching the primary DB and, for projects that
write-through to a replica, from causing a replica divergence that is painful to
recover from. Catch these locally, not mid-deploy.

> Language-agnostic: the same three invariants apply to any migration tool
> (Django, Flyway, Liquibase, Prisma Migrate, sqitch): (1) single active head,
> (2) every migration is reversible, (3) no unguarded destructive ops. Substitute
> your tool's `heads` / `status` command and grep over the files it generates.

## Workflow

### 1. Identify new migration files in this branch
```bash
# path glob: capabilities.migrations.versions_glob
git diff main...HEAD --name-only -- '*/versions/*'
```
If the output is empty, this skill is done — report `New migration files: none — done`
and skip steps 2–6.

> Only continue with steps 2–6 when step 1 found at least one file.

### 2. Confirm exactly one migration head
```bash
# kit.yaml → capabilities.migrations.heads_cmd
uv run alembic heads
```
More than one head means two branches added migrations independently and neither
created a merge migration. Fix: run `alembic merge heads -m "merge_heads"` and
commit the result before opening the PR.

### 3. Confirm every new migration has a `down_revision` and a non-trivial `downgrade()`
```bash
# List new files
NEW=$(git diff main...HEAD --name-only -- '*/versions/*')

# Flag any file where downgrade() body is only 'pass' (anchored to avoid false positives
# on comments containing "bypass", "password", etc.)
while IFS= read -r f; do
  grep -A 5 'def downgrade' "$f" | grep -qE '^[[:space:]]*pass[[:space:]]*$' && echo "TRIVIAL DOWNGRADE: $f"
done <<< "$NEW"
```
A `pass`-body `downgrade()` is not a downgrade — it is a trap. If rolling back
is genuinely impossible, that must be an explicit comment with a documented
runbook, not a silent no-op.

### 4. Flag destructive ops
```bash
git diff main...HEAD -- '*/versions/*' | grep -iE \
  '(DROP TABLE|DROP COLUMN|RENAME TABLE|RENAME COLUMN|ALTER.*TYPE|ALTER.*USING)'
```
Each hit requires a human decision. The standard mitigations:

| Pattern | Risk | Mitigation |
|---|---|---|
| `DROP TABLE` | data loss | verify backfill/archive landed in a prior migration, add safety check |
| `DROP COLUMN` | data loss | two-migration strategy: nullify → deploy → drop |
| `RENAME TABLE/COLUMN` | breaks readers | add alias view or migrate readers first |
| `ALTER COLUMN TYPE` (narrowing) | truncation / errors | widen first, backfill, narrow in follow-up |

### 5. Flag NOT NULL additions without a server_default or backfill
```bash
git diff main...HEAD -- '*/versions/*' | grep -iE 'NOT NULL|server_default|nullable=False'
```
Adding a NOT NULL column to a populated table without a `server_default` fails
on Postgres and SQLite alike. The safe sequence:
1. Add column as NULLABLE — deploy.
2. Backfill existing rows (in a separate migration or a data script).
3. Add `NOT NULL` constraint in a follow-up migration after backfill completes.

### 6. Flag data migrations on large tables (lock risk)
```bash
git diff main...HEAD -- '*/versions/*' | grep -iE \
  'op\.execute|connection\.execute|UPDATE|INSERT.*SELECT'
```
Bulk DML in a migration acquires locks for the full duration. Flag any
`UPDATE <table> SET ...` where the table could be large. Mitigation: batched
updates outside the migration (a background job), or `LOCK_TIMEOUT` + retry.

## Output

```
## Migration Check

- [ ] New migration files: <list or "none — done">
- [ ] Single head: <rev / MULTIPLE — merge needed>
- [ ] All downgrades non-trivial: <yes / FLAGGED: <files>>
- [ ] Destructive ops: <none / FLAGGED: <ops + files>>
- [ ] NOT NULL safety: <clean / FLAGGED: <columns + files>>
- [ ] Lock-risk DML: <none / FLAGGED: <tables + files>>

Verdict: PASS / BLOCK — <blocking issues with suggested fix>
```
