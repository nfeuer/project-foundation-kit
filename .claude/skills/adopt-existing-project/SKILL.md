---
name: adopt-existing-project
description: Non-destructively bring the foundation kit into an existing repo — audit what's already there, report gaps ranked by leverage, merge (never overwrite) kit artifacts, and recommend a phased rollout the team can approve incrementally
cost: cheap
protects: "The kit's guardrails get added to a repo already in flight without overwriting anything you wrote, and every change is shown as a diff you approve before it's applied."
requires: nothing
gate_key: none
ci_job: none
---

# Adopt Existing Project

Brings the foundation kit's guardrails into a repo that is already in flight.
The invariant is **non-destructive**: nothing the user authored is overwritten,
nothing is changed without an explicit dry-run diff and approval, and adoption
can be abandoned at any step without leaving the repo in a broken state.

Contrast with `new-project-bootstrap`, which writes from a blank slate. Here
you audit first, close only the gaps the team agrees to close, and roll out in
phases so the change is never all-or-nothing.

> Run every phase from the repo root. No changes are written until you confirm
> the dry-run output.

**Progress ledger.** Adoption spans phases and approval pauses — keep a ledger
at `.claude/scratch/adopt-existing-project-ledger.md` (see
`docs/PROGRESS_LEDGER.md`). Check for an existing ledger before starting and
resume from it (audit findings and per-phase approvals are the recorded
results); update it after every phase step; mark a phase awaiting human
approval as `BLOCKED`. Delete the ledger when adoption completes or is
explicitly abandoned.

---

## Workflow

### Phase 1 — Audit (change nothing)

Collect ground truth about what the repo already has. **Do not modify any
file.** Every command here is read-only.

#### 1.1 CI workflows
```bash
# kit.yaml inference — detect CI system and jobs
ls .github/workflows/ 2>/dev/null || echo "no GitHub Actions workflows"
ls .gitlab-ci.yml .circleci/ .buildkite/ 2>/dev/null || true
```
For each workflow file, list the job names and the commands they run (lint,
typecheck, test, build, deploy, etc.). Note which jobs are missing vs. the
kit's expected set: lint, typecheck, test, migration-heads, secrets-scan.

#### 1.2 `.claude/` scaffolding
```bash
ls .claude/ 2>/dev/null || echo "no .claude dir"
cat .claude/settings.json 2>/dev/null || echo "no settings.json"
```
Hook detection follows `settings.json` — a repo may keep hook scripts under
`scripts/hooks/`, `.claude/hooks/`, or any other directory and wire them via
`$CLAUDE_PROJECT_DIR` or absolute paths in `settings.json`. Do **not** assume
`.claude/hooks/` is the canonical location.

```bash
# Extract every hook command string from settings.json and resolve .sh paths
python3 - <<'PY'
import json, os, sys

try:
    data = json.load(open(".claude/settings.json"))
except Exception as e:
    print(f"no settings.json or parse error: {e}"); sys.exit(0)

# Walk the nested hooks structure: hooks.<Event>[{matcher, hooks:[{command}]}]
cmds = []
for hook_list in data.get("hooks", {}).values():
    for entry in (hook_list if isinstance(hook_list, list) else []):
        for h in (entry.get("hooks", []) if isinstance(entry, dict) else []):
            cmd = h.get("command", "") if isinstance(h, dict) else ""
            if cmd:
                cmds.append(cmd)

if not cmds:
    print("no hook commands found in settings.json")
    sys.exit(0)

print(f"{len(cmds)} hook command(s) found")
for cmd in cmds:
    for token in cmd.split():
        if token.endswith(".sh"):
            resolved = token.replace("$CLAUDE_PROJECT_DIR", ".") \
                            .replace("${CLAUDE_PROJECT_DIR}", ".")
            exists = os.path.isfile(resolved)
            executable = os.access(resolved, os.X_OK) if exists else False
            status = "executable" if executable else \
                     ("NOT EXECUTABLE" if exists else "MISSING")
            print(f"  {token} -> {status}")
PY
```
Record which named hooks are wired (`require-worktree`, `secret-scan-diff`,
`prune-merged-worktrees`, `post-merge-prune`, autoformat). Note any custom
hooks the repo has added — those must be preserved.

```bash
# P4: Portability — flag absolute paths in hook commands.
# Paths not anchored to $CLAUDE_PROJECT_DIR break on any other machine.
python3 - <<'PY'
import json, re, sys

try:
    data = json.load(open(".claude/settings.json"))
except Exception:
    sys.exit(0)

cmds = []
for hook_list in data.get("hooks", {}).values():
    for entry in (hook_list if isinstance(hook_list, list) else []):
        for h in (entry.get("hooks", []) if isinstance(entry, dict) else []):
            cmd = h.get("command", "") if isinstance(h, dict) else ""
            if cmd:
                cmds.append(cmd)

gaps = []
for cmd in cmds:
    for token in cmd.split():
        if re.match(r'^[/~]', token) and '$CLAUDE_PROJECT_DIR' not in token:
            gaps.append((token, cmd[:80]))

if gaps:
    for path, cmd_excerpt in gaps:
        print(f"  PORTABILITY GAP: absolute path '{path}'")
        print(f"    in command: {cmd_excerpt!r}")
        print(f"    -> use $CLAUDE_PROJECT_DIR/... for cross-machine portability")
else:
    print("no absolute paths in hook commands")
PY
```
Absolute paths in hook commands are a portability gap — record any found above
in the gap report (Phase 2).

#### 1.3 Docs taxonomy
```bash
ls docs/ 2>/dev/null || echo "no docs dir"
# followups.md may live at a non-standard path — search the whole tree
find . -name 'followups.md' -not -path '*/.git/*' | head
```
Check for: `docs/DOCS_STANDARD.md`, a `followups.md` anywhere in the tree
(may be at `docs/superpowers/specs/followups.md` or another non-standard path),
subdirs matching the kit's taxonomy (`architecture/`, `domain/`, `workflows/`,
`operations/`, `reference/`). Note any existing structure — adopt around it,
don't erase it.

#### 1.4 Test, lint, and type config
```bash
# Python
cat pyproject.toml 2>/dev/null | grep -A5 '\[tool\.'
cat setup.cfg 2>/dev/null | grep -A3 '\[mypy\]\|\[flake8\]\|\[pytest\]'
# Node
cat package.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(list(d.get('scripts',{}).items()))" 2>/dev/null
cat .eslintrc* tsconfig.json 2>/dev/null | head -20
# Go
cat Makefile 2>/dev/null | grep -E 'lint|test|vet|fmt'
```
Extract the real lint, typecheck, and test commands. These become the
`toolchain.*` values in the candidate profile — never replace them with kit
defaults.

#### 1.5 Spec file
```bash
ls spec*.md SPEC*.md docs/spec* README.md 2>/dev/null
```
Look for a canonical design document. If found, record its path — that becomes
`capabilities.spec.file`.

#### 1.6 Trunk branch
```bash
git remote show origin 2>/dev/null | grep 'HEAD branch'
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||'
```

#### 1.7 Package manager / toolchain
```bash
ls pyproject.toml uv.lock poetry.lock Pipfile requirements*.txt \
   package.json pnpm-lock.yaml yarn.lock bun.lockb \
   go.mod Cargo.toml 2>/dev/null
```
Pick the **first** matching file to determine the language and manager. Set
`toolchain.install` to the real install command (e.g. `npm ci`, `go mod download`,
`poetry install`).

#### 1.8 Logging reality check
```bash
# What does this repo actually log with? (see logging-init step 1 for the full probe)
grep -rEl --include='*.py' 'import (structlog|loguru)|import logging' src/ 2>/dev/null | head -3
grep -rEl --include='*.{js,ts}' "require\(['\"](pino|winston|bunyan)|from ['\"](pino|winston)" src/ lib/ 2>/dev/null | head -3
grep -rE --include='*.py' '^\s*print\(' src/ 2>/dev/null | wc -l
grep -rE --include='*.{js,ts}' 'console\.(log|error|warn)' src/ lib/ 2>/dev/null | wc -l
```
(Prune with `--exclude-dir={.git,.venv,node_modules,__pycache__,dist,build}`.)
Record the classification — GREENFIELD / PRINT-ONLY (with site count) /
PARTIAL / ESTABLISHED (library) — so the Phase 2 gap report states the logging
gap from evidence, not assumption. The fix is the **logging-init** skill in
Phase 4; do not wire anything now.

#### 1.9 Infer a candidate `kit.yaml`
From the evidence above, draft a `kit.yaml` using the real commands and the
best-fit preset (`library` / `service` / `llm-app` / `frontend` /
`data-pipeline`). Mark every field inferred vs. confirmed. Print it — do not
write it yet.

---

### Phase 2 — Gap Report

Produce a ranked table of what's missing relative to the kit's practices.
Rank by leverage (risk reduced × effort to close). For each gap, name the
exact skill or hook that closes it.

**Template:**

| # | Gap | Current state | Kit artifact that closes it | Effort |
|---|-----|--------------|----------------------------|--------|
| 1 | No worktree isolation | Agents edit `main` directly | `require-worktree.sh` hook + `parallel-work` skill | Low |
| 2 | No secrets scan on push | Secrets can reach the remote | `secret-scan-diff.sh` hook (PreToolUse on Bash) | Low |
| 3 | CI has lint but no typecheck | Type errors ship undetected | Add `typecheck` job to CI + `pre-pr` step 2 | Medium |
| 4 | No pre-PR gate | PRs go red after push | `pre-pr` skill | Low |
| 5 | No follow-ups log | Deferred decisions get lost | `docs/followups.md` + `followup-tracking` skill | Low |
| 6 | No spec-sync loop | Spec drifts from code silently | `doc-sync` skill + `spec-drift-checker` agent | Medium |
| 7 | No eval harness | Prompt behavior unverifiable | `eval-harness` + `prompt-regression` skills | High |
| 8 | No structured logging (per §1.8: print-only, 87 sites) | Failures may be swallowed; nothing is greppable | `logging-init` skill (probe → questions → wire) + `fallback_alert.py` | High |
| 9 | No nightly audit | Drift accumulates unnoticed | `nightly-audit` skill + cron | Medium |

Populate the table from the actual audit — omit rows where the repo already
satisfies the criterion. Reorder by actual leverage for this repo.

If §1.2 detected absolute paths in hook commands, add a row:
**Hook commands use absolute paths** | hardcoded `/home/…` or `/mnt/…` paths
in `settings.json` hook commands | replace with `$CLAUDE_PROJECT_DIR/…` in
each affected command string | Low.

---

### Phase 3 — Merge, Don't Overwrite

Apply each approved gap closure. Rules:

#### Settings / hooks — merge JSON, don't replace
If `.claude/settings.json` exists, add the kit's hook entries alongside the
existing ones — never replace the file. Show a diff:
```bash
# dry-run: what would be added to .claude/settings.json
python3 - <<'PY'
import json, sys
existing = json.load(open(".claude/settings.json"))
kit_hooks = <kit settings template content>
# merge: for each hook type (SessionStart, PreToolUse, PostToolUse),
# append kit entries that are not already present (compare by command string)
merged = merge_hooks(existing, kit_hooks)
print(json.dumps(merged, indent=2))
PY
```
Copy hook scripts that are absent; skip any that already exist under the same
name. If the repo has a custom hook at the same path, emit a warning — do not
overwrite.

#### CI — add missing jobs only
Read the existing workflow. Add only the jobs absent from it. Never delete or
rename existing jobs. Show a unified diff of the workflow file before writing.

#### CLAUDE.md — write only if absent; otherwise diff
```bash
if [ -f CLAUDE.md ]; then
  echo "CLAUDE.md exists — showing proposed additions only (review before applying)"
  diff CLAUDE.md <(cat "$KIT/CLAUDE.template.md")
else
  echo "CLAUDE.md absent — will write from template"
fi
```
Fill placeholders from the audit (`<stack>`, `<trunk_branch>`, `<spec_file>`,
etc.) before writing or diffing.

#### `kit.yaml` — write only if absent
```bash
if [ -f .claude/kit.yaml ]; then
  echo "kit.yaml exists — showing candidate profile for review; edit manually"
else
  echo "Writing inferred kit.yaml"
fi
```

#### Record the kit manifest
After the approved hooks/skills/agents/settings land, copy the source kit's
`.claude/kit-manifest.sha256` into the project's `.claude/`. It stamps the kit
version adopted here so `kit-update` can later distinguish a locally-modified
kit file from an untouched one instead of guessing (SPEC §12.1). Files the team
chose to keep their own version of will hash-mismatch this baseline and
correctly surface as NEEDS REVIEW on the next update — that is intended.
```bash
cp "$KIT/.claude/kit-manifest.sha256" .claude/kit-manifest.sha256
```

#### Docs and follow-ups — add, never clobber
- `docs/DOCS_STANDARD.md`: copy if absent.
- `docs/followups.md`: copy if absent; if present, append a `## Kit Adoption` section with the gap items as open follow-ups.
- Subdirs (`docs/domain/`, `docs/workflows/`, etc.): `mkdir -p` only — never touch existing files inside them.

#### Idempotency
Every write step checks for prior existence before acting. Re-running the skill
after a partial adoption produces only the remaining changes, never duplicates.

#### Dry-run default
All changes above are printed as diffs and confirmed with the user before any
file is written. Run with an explicit `--apply` flag (or user confirmation) to
commit them.

---

### Phase 4 — Incremental Rollout

Never present adoption as a single big-bang change. Recommend phases, each
independently valuable, each requiring explicit human approval before the next.

**Phase 1 — Safety net (1–2 hours, zero collaboration risk)**
- Hooks: `secret-scan-diff` on Bash push/PR-create.
- Hooks: `prune-merged-worktrees` + `post-merge-prune` (safe on any repo).
- Skills: `pre-pr`, `ci-watch`, `branch-conflict-check`.
- Outcome: no PR arrives red; no secret leaks; branch queue stays healthy.
- No behavior visible to collaborators who don't use Claude Code.

**Phase 2 — Worktree isolation (coordinate with collaborators first)**
- Hook: `require-worktree` blocking edits on trunk.
- Skill: `parallel-work` for concurrent sessions.
- Outcome: agents never race on the same file.
- **This phase changes behavior for everyone using Claude Code on the repo.**
  Flag it to the team before enabling. On a solo repo, enable freely.

**Phase 3 — Doc / spec loop**
- Skills: `doc-sync`, `followup-tracking`, `session-handoff`.
- Agents: `spec-drift-checker`, `docs-updater`.
- `capabilities.spec.file` set in `kit.yaml`.
- Outcome: every PR keeps docs and spec in sync; deferred decisions are tracked.

**Phase 4 — Observability and evaluation**
- Skills: `logging-init` (driven by the §1.8 classification — asks its three
  questions, then wires additively; ESTABLISHED repos keep their library),
  `eval-harness`, `prompt-regression`, `cost-check`, `nightly-audit`.
- Agents: `observability-reviewer`, `test-gap-analyzer`.
- Reference implementations: `fallback_alert.py` (logging itself comes via
  `logging-init`).
- Outcome: LLM behavior is verifiable; costs are tracked; silent failures are
  eliminated; a morning digest flags drift before it compounds.

Each phase can be the end state if the team decides the later phases aren't
worth the overhead for their context.

---

## Guardrails

**Never enable `require-worktree` silently on a shared repo.**
It blocks edits on trunk for *every* Claude Code user on the repo, not just
you. Always flag this to the team and get explicit buy-in before Phase 2.

**Never overwrite a file the user authored.**
If a file exists — `CLAUDE.md`, `settings.json`, `.github/workflows/ci.yml`,
any hook script — show a diff and require confirmation. Writing without review
is forbidden.

**Preserve existing tool commands.**
If the repo uses `npm run test`, `make lint`, or `cargo test`, those go into
`toolchain.*` in `kit.yaml` verbatim. Never substitute `uv run pytest` or any
other kit default without explicit instruction.

**Recover custom hooks into `kit.yaml`.**
If the repo has its own hooks or Makefile targets that the kit would duplicate,
note them in the audit and wire them through the profile rather than installing
parallel commands.

**Autoformat hook: match the language.**
The PostToolUse autoformat defaults to `ruff`. Before installing it, confirm
the repo's formatter (`prettier`, `gofmt`, `rustfmt`) and substitute the
correct command. Installing the wrong formatter silently reformats code.

---

## Output

```
## Adopt Existing Project

### Audit Summary
- Repo: <name> | Trunk: <branch> | Stack: <language + package manager>
- Preset inferred: <preset>
- CI system: <GitHub Actions / GitLab CI / none> | Jobs found: <list>
- .claude/ present: <yes | no>
- settings.json: <present (N hook commands) | absent>
- Hooks wired (from settings.json): <list — each: executable / NOT EXECUTABLE / MISSING | none>
- Absolute paths in hook commands: <none | list of portability gaps>
- CLAUDE.md: <present | absent>
- Docs: <dir present — DOCS_STANDARD: yes/no, followups: yes/no (path if non-standard) | absent>
- Spec file: <path | none detected>
- Logging: <ESTABLISHED (<library>) | PARTIAL | PRINT-ONLY (N sites) | GREENFIELD>
- Toolchain detected: lint=<cmd>, typecheck=<cmd>, test=<cmd>, install=<cmd>
- Candidate kit.yaml: <printed above — review and confirm>

### Gap Report (ranked by leverage)
| # | Gap | Skill/hook that closes it | Effort |
|---|-----|--------------------------|--------|
| 1 | ... | ... | ... |
| N | ... | ... | ... |

### Proposed Changes (dry-run — nothing written yet)
- .claude/settings.json: <merge N hook entries — diff shown above>
- .claude/hooks/: <copy: require-worktree.sh, secret-scan-diff.sh | skip: already present>
- .claude/kit-manifest.sha256: <record — baseline for kit-update classification>
- .github/workflows/ci.yml: <add jobs: typecheck, migration-heads — diff shown above>
- CLAUDE.md: <absent — will write from template | present — proposed diff shown above>
- .claude/kit.yaml: <absent — will write | present — candidate profile shown for review>
- docs/DOCS_STANDARD.md: <copy | skip — present>
- docs/followups.md: <copy | append Kit Adoption section>
Confirm to apply? (y/N)

### Phased Rollout
Phase 1 (Safety net — apply now, no collaboration risk):
  [ ] secret-scan-diff hook
  [ ] prune-merged-worktrees + post-merge-prune hooks
  [ ] pre-pr, ci-watch, branch-conflict-check skills

Phase 2 (Worktree isolation — coordinate with team first):
  [ ] require-worktree hook  ← BEHAVIOR CHANGE for all Claude Code users
  [ ] parallel-work skill

Phase 3 (Doc / spec loop):
  [ ] doc-sync, followup-tracking, session-handoff skills
  [ ] spec-drift-checker, docs-updater agents
  [ ] capabilities.spec.file set in kit.yaml

Phase 4 (Observability + eval):
  [ ] eval-harness, prompt-regression, cost-check, nightly-audit skills
  [ ] observability-reviewer, test-gap-analyzer agents
  [ ] logging_setup.py + fallback_alert.py reference impls

Human approves each phase before the next begins.
```
