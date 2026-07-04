# The Progress Ledger

Long multi-step kit operations — `new-project-bootstrap`, `adopt-existing-project`,
`kit-update` — can be interrupted: a session ends, context runs out, a step
blocks on a human answer. Without durable state, the next session either redoes
finished steps (wasteful, and not always idempotent) or guesses where things
stood (worse). The ledger is the fix: a small machine-checkable task list the
skill updates as it goes, so any session can resume exactly where the last one
stopped.

Where `session-handoff` writes a narrative baton note for a *person or agent*,
the ledger is structured state for a *skill re-run*. Long skills use both: the
ledger for step state, a handoff note for context when stopping deliberately.

## Location

`.claude/scratch/<skill-name>-ledger.md` — one ledger per skill run.
`.claude/scratch/` is git-ignored (bootstrap adds it alongside
`.claude/worktrees/`); ledgers are working state, never committed.

## Format

```markdown
# <skill-name> ledger
- Repo: <name>   Started: <YYYY-MM-DD>   Args: <flags, e.g. --apply>

## Steps
- [x] 1. Detect stack — DONE — python/uv, trunk=main, ui subdir: none
- [x] 2. Select preset — DONE — llm-app (auto)
- [x] 3. Write kit.yaml — DONE_WITH_CONCERNS — perf budgets left at TODO
- [ ] 4. Install .claude scaffolding — BLOCKED — settings.json exists with
      custom hooks; awaiting user decision on merge
- [ ] 5. Author CLAUDE.md — PENDING
```

One line per step, numbered to match the skill's workflow. Each carries a
status and a short result — the result is what makes resume possible without
re-deriving (record *decisions and detected values*, not prose).

## Statuses

| Status | Meaning | On resume |
|---|---|---|
| `PENDING` | Not started | Run it |
| `DONE` | Completed and verified | Skip; trust the recorded result |
| `DONE_WITH_CONCERNS` | Completed, but something needs eventual attention | Skip, but surface the concern in the final report |
| `BLOCKED` | Cannot proceed without input or an external event | Ask / check the blocker first — this is the resume point |
| `NEEDS_CONTEXT` | Step needs information a fresh session won't have | Re-gather the named context before running |

## Rules

- **Update after every step**, not at the end — a ledger written at the end
  protects nothing.
- **On invocation, check for a ledger first.** If one exists for this skill,
  read it, skip `DONE` steps, and resume at the first non-DONE step. Confirm
  recorded values still hold if the repo may have changed since (`git log
  --oneline -5` since the ledger's start date is a cheap sanity check).
- **Delete the ledger when the run completes** and its final report is emitted.
  A lingering ledger means an unfinished run — `kit-doctor` treats one older
  than 7 days as a WARN.
- Never store secrets in a ledger; record *where* a credential lives, not its
  value.
