---
name: new-project-bootstrap
description: Lay a strong foundation in a new or existing repo — install worktree isolation, autoformat, CI, CLAUDE.md, docs standard, follow-ups log, and the observability/eval/doc-sync scaffolding from the foundation kit
---

# New Project Bootstrap

Installs the foundation kit into a repo so it starts with the guardrails that
otherwise get bolted on late (or never): concurrent-agent isolation, no-silent-
failure logging, a spec/doc/drift sync loop, follow-up tracking, an eval harness,
and a CI gate that agents keep green. Run this once per new project.

## Workflow

### 1. Confirm scope
Ask the user (only what you can't infer): primary language/stack, whether it's a
deployed service (needs the operations/observability stack) or a library, and
whether it has a canonical design spec. Infer the rest from the repo.

### 2. Install the `.claude/` scaffolding
Copy from the kit into the target repo:
```bash
KIT=<path-to>/project-foundation-kit
DEST=<target-repo>
cp -r "$KIT/.claude/hooks" "$DEST/.claude/hooks"
cp "$KIT/.claude/settings.template.json" "$DEST/.claude/settings.json"
cp -r "$KIT/.claude/skills/"* "$DEST/.claude/skills/"
cp -r "$KIT/.claude/agents/"* "$DEST/.claude/agents/"
chmod +x "$DEST/.claude/hooks/"*.sh
mkdir -p "$DEST/.claude/worktrees"
printf '%s\n' '.claude/worktrees/' >> "$DEST/.gitignore"
```
Adjust `settings.json`: keep the worktree + secret-guard hooks as-is; swap the
PostToolUse autoformat command to match the language (ruff / prettier / gofmt).

### 3. Author CLAUDE.md
Copy `CLAUDE.template.md` → `CLAUDE.md` and fill in every `<...>`. Keep it under
~200 lines. Pull the real directory layout from the repo. State the design
principles as non-negotiables. This file loads into every session — make it count.

### 4. Install docs + tracking
```bash
cp "$KIT/docs/DOCS_STANDARD.md" "$DEST/docs/DOCS_STANDARD.md"
cp "$KIT/docs/followups.template.md" "$DEST/docs/followups.md"
```
Run the `doc-sync` skill in `init` mode to scaffold the docs taxonomy from the
repo's structure and git log.

### 5. Install CI
```bash
cp "$KIT/.github/workflows/ci.template.yml" "$DEST/.github/workflows/ci.yml"
```
Edit the run steps to the real toolchain. Confirm each CI job has a matching step
in the `pre-pr` skill — that equivalence is what keeps PRs green on first push.

### 6. Wire the reference implementations
For the language that applies, adapt from `templates/`:
- `logging_setup.py` — structured logging, dual render, correlation context.
- `fallback_alert.py` — the no-silent-failure pattern (`emit_fallback_alert`).
- `eval_fixture.example.json` — the tiered fixture shape under `fixtures/`.

### 7. Verify the foundation
- Confirm the worktree hook blocks an edit on `main` (try one; expect the block).
- Confirm the autoformat hook runs on save.
- Open a throwaway branch, push, and confirm CI runs.
- Run `pre-pr` on an empty change to confirm the gate wiring.

## Output
```
## Bootstrap Complete
- Hooks: worktree-isolation, secret-guard, secret-scan-diff, autoformat, merge-prune — installed
- Skills: <list> — installed
- Agents: <list> — installed
- CLAUDE.md: authored (<n> lines)
- Docs: DOCS_STANDARD + followups + taxonomy scaffolded
- CI: ci.yml installed (<jobs>)
- Reference impls wired: <logging / fallback / eval>
- Verification: <worktree block OK / autoformat OK / CI runs OK / pre-pr OK>
Next: create a feature worktree (parallel-work skill) and start building.
```
