---
name: new-project-bootstrap
description: Lay a strong foundation in a new or existing repo — detect the stack, write the project profile (kit.yaml), install worktree isolation, autoformat, CI, CLAUDE.md, docs standard, follow-ups log, and the observability/eval/doc-sync scaffolding from the foundation kit
---

# New Project Bootstrap

Installs the foundation kit into a repo so it starts with the guardrails that
otherwise get bolted on late (or never): concurrent-agent isolation, no-silent-
failure logging, a spec/doc/drift sync loop, follow-up tracking, an eval harness,
and a CI gate that agents keep green. Run this once per new project.

## Workflow

### 1. Detect the stack

Probe the repo root for manifests, CI, and Makefile. Do not guess — let the repo
answer.

```bash
# Language / manifest (root)
ls pyproject.toml package.json go.mod Cargo.toml 2>/dev/null

# UI sub-project — scan subdirs for a nested package.json (Python root + JS sub-app pattern)
find . -maxdepth 3 -name package.json ! -path '*/node_modules/*' \
  | grep -v '^\./package\.json'
# Record any subdir paths returned — used when writing capabilities.ui in step 3

# Lock files (disambiguate npm vs pnpm vs yarn)
ls package-lock.json pnpm-lock.yaml yarn.lock 2>/dev/null

# CI commands — scan first workflow for lint/test/build run steps
cat .github/workflows/*.yml 2>/dev/null | head -150

# Makefile targets
cat Makefile 2>/dev/null | grep -E '^[a-z].*:' | head -30

# Trunk branch
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
  || git branch -r | grep -E 'HEAD|main|master' | head -1
```

Record: language, package manager, the exact lint/format/typecheck/test/build
commands, the trunk branch name, and any subdirectory `package.json` paths found.
Flag any command not yet present — you will need it for step 3.

### 2. Select a preset

Map detected evidence to one of the five archetypes in `presets/`:

| Detected | Preset |
|---|---|
| `pyproject.toml`, no DB migration files, no server entrypoint | `library` |
| Python + migration files, no LLM imports | `service` |
| Python + LLM API calls (`anthropic`, `openai`, etc.) | `llm-app` |
| `package.json` + DOM/React/Vue/Svelte | `frontend` |
| Python + migration files + scheduled batch jobs | `data-pipeline` |

If the mapping is ambiguous, ask the user once; otherwise proceed without asking.

### 3. Write `.claude/kit.yaml`

Load `presets/<chosen>.yaml` as the starting point. Overlay every value you
detected in step 1 on top of the preset defaults — detected commands always win.
Fill in `trunk_branch`, all non-empty `toolchain.*` entries, and any capability
flags the repo evidence implies (e.g., `capabilities.migrations.enabled: true` if
migration files exist).

```bash
KIT=<path-to>/project-foundation-kit
DEST=<target-repo>
mkdir -p "$DEST/.claude"
cp "$KIT/presets/<chosen>.yaml" "$DEST/.claude/kit.yaml"
# Now patch kit.yaml with the detected values:
#   - trunk_branch
#   - toolchain.lint / format / typecheck / test / test_integration / build / install
#   - capability toggles that differ from the preset default
# Annotate any field left at its preset default with a  # TODO  comment so the
# user knows what still needs verification.
```

Review the written file before continuing. Every non-empty `toolchain.*` command
must actually exist in the repo. Every capability toggle must match what is
installed.

UI sub-project: if step 1 found a `package.json` in a subdirectory (e.g.
`donna-ui/`), set `capabilities.ui.enabled: true` and derive `build_cmd` /
`typecheck_cmd` from that subdir's `scripts` block — prefix each with
`cd <subdir> &&` so it runs from the repo root. Set `typecheck_cmd` only if a
`tsc`, `typecheck`, or `type-check` script entry exists; otherwise leave it empty.

```bash
# Inspect the sub-project's available scripts
python3 -c "import json; s=json.load(open('<subdir>/package.json')).get('scripts',{}); [print(k,':', v) for k,v in s.items()]"
```

Ratchet guards: set `capabilities.coverage.ratchet_enabled: true` ONLY if
`.coverage-baseline` already exists in the repo; otherwise write `false` with a
`# TODO: run the baseline command, then flip on` annotation. Apply the same guard
to `capabilities.perf.enabled` against `.perf-baseline`. Enabling a ratchet with
no baseline makes kit-doctor WARN on every run immediately after install.

```bash
[ -f .coverage-baseline ] || echo "  ratchet_enabled: false  # TODO: generate baseline, then flip to true"
[ -f .perf-baseline ]     || echo "  perf.enabled: false     # TODO: generate baseline, then flip to true"
```

Migration glob: derive `capabilities.migrations.versions_glob` from `alembic.ini`'s
`script_location` rather than using the preset wildcard `*/versions/*.py`.

```bash
grep -E '^script_location\s*=' alembic.ini 2>/dev/null | cut -d= -f2 | tr -d ' '
# e.g. "alembic" → set versions_glob: "alembic/versions/*.py"
```

Fall back to `*/versions/*.py` only when `alembic.ini` is absent. For
`toolchain.format`, use the same runner prefix as the rest of the toolchain — on a
`uv` project write `uv run ruff format`, not bare `ruff format`.

### 4. Install the `.claude/` scaffolding

```bash
cp -r "$KIT/.claude/hooks"                  "$DEST/.claude/hooks"
cp    "$KIT/.claude/settings.template.json" "$DEST/.claude/settings.json"
cp -r "$KIT/.claude/skills/"*              "$DEST/.claude/skills/"
cp -r "$KIT/.claude/agents/"*              "$DEST/.claude/agents/"
chmod +x "$DEST/.claude/hooks/"*.sh
mkdir -p "$DEST/.claude/worktrees"
printf '%s\n' '.claude/worktrees/' >> "$DEST/.gitignore"
```

Adjust `settings.json`: keep the worktree + secret-guard hooks as-is; swap the
PostToolUse autoformat command to match the toolchain (ruff / prettier / gofmt).

### 5. Author CLAUDE.md

Copy `CLAUDE.template.md` → `CLAUDE.md` and fill in every `<...>`. Keep it under
~200 lines. Pull the real directory layout from the repo. State the design
principles as non-negotiables. This file loads into every session — make it count.

### 6. Install docs + tracking

```bash
cp "$KIT/docs/DOCS_STANDARD.md"      "$DEST/docs/DOCS_STANDARD.md"
cp "$KIT/docs/followups.template.md" "$DEST/docs/followups.md"
```

Run the `doc-sync` skill in `init` mode to scaffold the docs taxonomy from the
repo's structure and git log.

### 7. Install CI

```bash
cp "$KIT/templates/ci.template.yml" "$DEST/.github/workflows/ci.yml"
```

Edit the run steps to the real toolchain commands (same values as `kit.yaml`).
Confirm each CI job has a matching step in the `pre-pr` skill — that equivalence
is what keeps PRs green on first push.

### 8. Wire the reference implementations

For the language that applies, adapt from `templates/`:
- `logging_setup.py` — structured logging, dual render, correlation context.
- `fallback_alert.py` — the no-silent-failure pattern (`emit_fallback_alert`).
- `eval_fixture.example.json` — the tiered fixture shape under `fixtures/`.

### 9. Verify the foundation

- Confirm the worktree hook blocks an edit on `main` (try one; expect the block).
- Confirm the autoformat hook fires on save.
- Open a throwaway branch, push, and confirm CI runs.
- Run `pre-pr` on an empty change to confirm the gate wiring.
- Run each non-empty `toolchain.*` command from `kit.yaml` and confirm exit 0.

## Output

```
## Bootstrap Complete
- Stack detected: <language>, <package manager>, trunk: <branch>
- Preset: <name> (auto-detected | chosen by user)
- kit.yaml: written — <N> toolchain commands set, <M> capabilities enabled
- Hooks: worktree-isolation, secret-guard, secret-scan-diff, autoformat, merge-prune — installed
- Skills: <list> — installed
- Agents: <list> — installed
- CLAUDE.md: authored (<n> lines)
- Docs: DOCS_STANDARD + followups + taxonomy scaffolded
- CI: ci.yml installed (<jobs>)
- Reference impls wired: <logging / fallback / eval>
- Verification: <worktree block OK / autoformat OK / CI runs OK / pre-pr OK>
Next: run kit-doctor to verify the wiring, then create a feature worktree (parallel-work skill) and start building.
```
