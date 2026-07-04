---
name: doc-sync
description: Keep docs, spec, and code in lockstep in the same PR — update affected narrative docs, cite/update the canonical spec, and log any accepted drift as a follow-up
---

# Doc Sync

**Profile-driven.** Narrative doc paths use `capabilities.docs.dir` from `.claude/kit.yaml` (default: `docs/`). Spec checks reference `capabilities.spec.file` — if that key is empty, steps 3 (cite/sync spec) and the citation gate are skipped.

Documentation drifts the moment code changes and the docs don't. This skill runs
at the end of a change (it's step 6–8 of the `pre-pr` gate) and closes the gap
across three surfaces: **narrative docs**, the **canonical spec**, and the
**follow-ups log**. Read `docs/DOCS_STANDARD.md` for the taxonomy before you
start.

## Search hygiene

- Broad `grep` and `find` must prune stale and generated trees to avoid false positives.
- Always pass `--exclude-dir={.git,.venv,node_modules,__pycache__,.claude/worktrees,dist,build}` (or the `find -prune` equivalent).
```bash
grep -r ... --exclude-dir={.git,.venv,node_modules,__pycache__,.claude/worktrees,dist,build}
```

## Workflow

### 1. Diff the branch
```bash
git diff main...HEAD --name-only
```
This is the universal starting point — map each changed source file to the docs
it affects.

### 2. Update narrative docs (hand-written)
For each changed area, update the relevant hand-written pages under
`capabilities.docs.dir` (default: `docs/`):
- `<docs.dir>/domain/<subsystem>.md` — if behavior or data model changed.
- `<docs.dir>/workflows/<flow>.md` — if a user-facing flow changed.
- `<docs.dir>/operations/*` — if deployment, migrations, or monitoring changed.
- `<docs.dir>/changelog.md` — always, for a user-visible change.
- `<docs.dir>/troubleshooting.md` / `glossary.md` — if you introduced a new failure
  mode or domain term.

**Never hand-edit generated pages** (`docs/reference/`, `docs/config/`,
`docs/schemas/`) — those regenerate from docstrings/config on build. Instead, fix
the docstring or config that generates them.

Each domain page opens with a one-line summary and a `> Realizes: <spec> §X.Y`
citation.

### 3. Cite and sync the spec
**Skipped when `capabilities.spec.file` is empty in `kit.yaml`.** Otherwise, every
design change cites the spec section it implements (`capabilities.spec.file`). If
behavior now diverges from what the spec says:
- **In scope:** update the affected `§` in this same PR.
- **Out of scope:** call it out explicitly in the PR body **and** log a follow-up
  (next step) with status `spec-update-pending`. Never let it drift silently.

Use the `spec-check` skill (or the **spec-drift-checker** agent) for the detailed
file→section audit.

### 4. Log follow-ups
Scan the diff for TODOs, deferred decisions, and accepted drift. Append them to
`docs/followups.md` (see the `followup-tracking` skill for the entry format).
Close any follow-up this PR resolves by moving it to the archive.

### 5. Verify links
Check that internal doc links you touched still resolve. A moved or renamed page
breaks references silently.

## Output
```
## Doc Sync
- Narrative pages updated: <list / none affected>
- Generated pages: <regenerate on build / N/A>
- Spec: <cited §X.Y / updated §X.Y / follow-up logged for §X.Y>
- Follow-ups: <added N / closed N / none>
- Links: <clean / fixed N>
```
